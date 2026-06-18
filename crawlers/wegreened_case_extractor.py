"""WeGreened approval-digest per-case extractor.

Each "Latest-Information" digest article (e.g. "58 I-140 Approvals on June 3,
2026") bundles dozens of individually-numbered approval write-ups in prose
form. This module sends each article's text to a Groq LLM and parses out one
structured analytics record per case (category, field, applicant profile,
evidence profile, adjudication info) — see wegreened_crawl_spec.md section 2.3
for the field rationale.

This is a separate artifact from wegreened_crawler.py: that module produces
flat KnowledgeChunk-shaped text for the Neo4j RAG pipeline; this module
produces structured per-case rows for analytics (citation thresholds,
processing-time distributions, etc.) and is intentionally NOT wired into
json_importer.py / Neo4j — storage backend (Postgres/AstraDB/etc.) is
deferred. Output: one JSON array per crawl day under
data/crawled/wegreened_cases/, plus a consolidated CSV regenerated each run.
"""
from __future__ import annotations
import csv
import json
import logging
import os
import re
import time
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from crawlers.wegreened_crawler import SITE_BASE, fetch_all_news_articles, html_to_text

load_dotenv()
logger = logging.getLogger(__name__)

_REQUEST_DELAY = 2.5  # seconds between Groq calls -- stays under ~30 req/min free tier

_CATEGORY_ALIASES = {
    "EB1A": "EB1-A", "EB-1A": "EB1-A", "EB1-A": "EB1-A",
    "EB1B": "EB1-B", "EB-1B": "EB1-B", "EB1-B": "EB1-B",
    "EB1C": "EB1-C", "EB-1C": "EB1-C", "EB1-C": "EB1-C",
    "EB2NIW": "EB2-NIW", "EB2-NIW": "EB2-NIW", "EB-2NIW": "EB2-NIW", "NIW": "EB2-NIW",
}

_DATE_RE = re.compile(r"on\s+([A-Za-z]+\.?\s+\d{1,2},?\s*\d{4})", re.IGNORECASE)

_SYSTEM_PROMPT = """\
You are a precise data-extraction assistant for U.S. employment-based immigration \
approval announcements (EB-1A, EB-1B, EB-1C, EB2-NIW). The user will give you the \
full text of a digest article describing one or more individually-numbered approved \
cases. Extract EVERY case into a JSON array. Return ONLY the JSON array -- no \
markdown, no explanation, no surrounding text.

Each case object must have exactly these fields (use null for anything not stated \
in the text; booleans must be true/false; counts must be integers):
{
  "case_number": int,
  "category": "EB1-A" | "EB1-B" | "EB1-C" | "EB2-NIW",
  "field": string,
  "country_birth": string,
  "residence_during_filing": string,
  "residing_outside_us": bool,
  "degree": string,
  "current_role": string,
  "proposed_role": string,
  "sector": "academia" | "industry" | "other",
  "publications": int,
  "citations": int,
  "rec_letters": int,
  "testimonial_letters": int,
  "service_center": string,
  "premium_processing": "upfront" | "upgrade" | "none",
  "processing_days": int,
  "notable": array of zero or more strings from ["approved_without_letters", "non_stem", "no_phd"]
}

If the article describes only a single, unnumbered case, return a single-element \
array with case_number 1."""

CSV_COLUMNS = [
    "source_url", "crawl_date", "approval_date", "article_title", "case_number",
    "category", "field", "country_birth", "residence_during_filing",
    "residing_outside_us", "degree", "current_role", "proposed_role", "sector",
    "publications", "citations", "rec_letters", "testimonial_letters",
    "total_letters", "no_letters", "service_center", "premium_processing",
    "processing_days", "had_rfe", "notable",
]


def _parse_approval_date(title: str) -> str | None:
    m = _DATE_RE.search(title)
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _normalize_category(value: str | None) -> str | None:
    if not value:
        return None
    return _CATEGORY_ALIASES.get(value.strip().upper().replace(" ", ""), value.strip())


def _load_seen(seen_file: Path) -> set[str]:
    if seen_file.exists():
        try:
            return set(json.loads(seen_file.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()


def _save_seen(seen_file: Path, seen: set[str]) -> None:
    seen_file.parent.mkdir(parents=True, exist_ok=True)
    seen_file.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_cases(client: Groq, model: str, article_text: str) -> list[dict]:
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": article_text[:40000]},
            ],
            temperature=0,
            max_tokens=16000,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"```[a-z]*\n?", "", raw).strip("` \n")
        cases = json.loads(raw)
        if isinstance(cases, dict):
            cases = cases.get("cases", [cases])
        return cases if isinstance(cases, list) else []
    except Exception as exc:
        logger.warning("[wegreened_cases] extraction failed: %s", exc)
        return []


def _is_empty_case(case: dict) -> bool:
    """True for placeholder cases the LLM emits when an article has no per-case
    breakdown (e.g. a pure yearly/monthly approval-count summary)."""
    return not any(
        case.get(f) for f in ("category", "field", "country_birth", "degree", "current_role", "proposed_role")
    )


def _build_case_record(
    case: dict, article: dict, crawl_date: str, approval_date: str | None, had_rfe: bool,
) -> dict:
    rec = case.get("rec_letters")
    test = case.get("testimonial_letters")
    total_letters = (rec or 0) + (test or 0) if (rec is not None or test is not None) else None
    no_letters = total_letters == 0 if total_letters is not None else False

    notable = list(case.get("notable") or [])
    notable.append("approved_after_rfe" if had_rfe else "no_rfe")

    return {
        "source_url": f"{SITE_BASE}/Latest-Information/{article.get('slug', '')}",
        "crawl_date": crawl_date,
        "approval_date": approval_date,
        "article_title": article.get("title", ""),
        "case_number": case.get("case_number"),
        "category": _normalize_category(case.get("category")),
        "field": case.get("field"),
        "country_birth": case.get("country_birth"),
        "residence_during_filing": case.get("residence_during_filing"),
        "residing_outside_us": bool(case.get("residing_outside_us", False)),
        "degree": case.get("degree"),
        "current_role": case.get("current_role"),
        "proposed_role": case.get("proposed_role"),
        "sector": case.get("sector"),
        "publications": case.get("publications"),
        "citations": case.get("citations"),
        "rec_letters": rec,
        "testimonial_letters": test,
        "total_letters": total_letters,
        "no_letters": no_letters,
        "service_center": case.get("service_center"),
        "premium_processing": case.get("premium_processing"),
        "processing_days": case.get("processing_days"),
        "had_rfe": had_rfe,
        "notable": notable,
    }


def _append_records(out_file: Path, records: list[dict]) -> None:
    if not records:
        return
    existing = []
    if out_file.exists():
        try:
            existing = json.loads(out_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    out_file.write_text(
        json.dumps(existing + records, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def _rebuild_csv(out_base: Path, csv_file: Path) -> None:
    rows: list[dict] = []
    for f in sorted(out_base.glob("*.json")):
        if f.name == "seen_articles.json":
            continue
        try:
            rows.extend(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue

    with open(csv_file, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            row = dict(r)
            row["notable"] = "|".join(row.get("notable") or [])
            writer.writerow(row)


def run(out_dir: str = "data/crawled", limit: int | None = None) -> int:
    """limit caps how many NEW (not-yet-seen) articles are processed in this call --
    useful to spread a large rate-limited backfill across multiple runs, or to
    preview output quickly. Already-seen articles don't count against it."""
    out_base = Path(out_dir) / "wegreened_cases"
    out_base.mkdir(parents=True, exist_ok=True)
    seen_file = out_base / "seen_articles.json"
    csv_file = out_base / "cases.csv"

    seen = _load_seen(seen_file)
    articles = fetch_all_news_articles()
    logger.info("[wegreened_cases] %d articles fetched, %d already processed", len(articles), len(seen))

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    model = os.environ.get("GROQ_MODEL") or "llama3-70b-8192"

    crawl_date = date.today().isoformat()
    out_file = out_base / f"{crawl_date}.json"
    total_new = 0
    processed = 0

    # Saved after every article (not batched to the end) so a mid-run kill --
    # e.g. a CI job timeout while waiting out a Groq 429 backoff -- doesn't
    # discard already-paid-for LLM calls.
    for article in articles:
        if limit is not None and processed >= limit:
            break

        slug = article.get("slug") or str(article.get("id", ""))
        if not slug or slug in seen:
            continue
        processed += 1

        text = html_to_text(article.get("content", ""))
        if len(text) < 50:
            seen.add(slug)
            _save_seen(seen_file, seen)
            continue

        cases = _extract_cases(client, model, text)
        time.sleep(_REQUEST_DELAY)
        if not cases:
            logger.warning("[wegreened_cases] no cases extracted for %s, will retry next run", slug)
            continue  # not marked seen -> retried on next run

        title = article.get("title", "")
        had_rfe = "rfe" in title.lower()
        approval_date = _parse_approval_date(title)

        records = [
            _build_case_record(case, article, crawl_date, approval_date, had_rfe)
            for case in cases
            if not _is_empty_case(case)
        ]
        seen.add(slug)

        _append_records(out_file, records)
        _save_seen(seen_file, seen)
        _rebuild_csv(out_base, csv_file)
        total_new += len(records)

    logger.info("[wegreened_cases] saved %d new case records -> %s", total_new, out_file)
    return total_new
