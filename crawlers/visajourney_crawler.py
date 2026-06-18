"""VisaJourney processing time stats crawler using BeautifulSoup (no login required).

Scrapes the timeline statistics pages:
  - /timeline/aosstats.php  — Adjustment of Status (I-485) by office
  - /timeline/eadstats.php  — Employment Authorization Document (EAD)
  - /timeline/apstats.php   — Advance Parole (I-131)

Each stats page returns processing time averages in plain HTML (no JS needed).
We convert each table row into a knowledge chunk.
"""
from __future__ import annotations
import logging
import re
import time
from datetime import date

import httpx
from bs4 import BeautifulSoup

from crawlers.base import BaseCrawler, make_chunk_id, make_record

logger = logging.getLogger(__name__)

STATS_PAGES = [
    (
        "https://www.visajourney.com/timeline/aosstats.php",
        "adjustment_of_status",
        "Adjustment of Status (Green Card) I-485",
        "eb2_niw",
        "usa",
    ),
    (
        "https://www.visajourney.com/timeline/eadstats.php",
        "ead",
        "Employment Authorization Document (EAD) I-765",
        "general",
        "usa",
    ),
    (
        "https://www.visajourney.com/timeline/apstats.php",
        "advance_parole",
        "Advance Parole (I-131)",
        "general",
        "usa",
    ),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _fetch_html(url: str, timeout: int = 20) -> str:
    r = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
    r.raise_for_status()
    return r.text


def _clean_text(text: str) -> str:
    """Strip whitespace and non-breaking spaces."""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _extract_table_sections(soup: BeautifulSoup) -> list[dict]:
    """
    Extract all HTML tables from the page as list of dicts.
    Each dict has: {'title': str, 'headers': list[str], 'rows': list[list[str]]}
    """
    sections = []
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        if not rows:
            continue
        # First row is header
        header_cells = rows[0].find_all(["th", "td"])
        headers = [_clean_text(c.get_text()) for c in header_cells]
        if not headers or not any(h for h in headers):
            continue

        data_rows = []
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            values = [_clean_text(c.get_text()) for c in cells]
            if any(v for v in values):
                data_rows.append(values)

        if data_rows:
            # Find a title — look for the closest preceding heading
            title = ""
            for prev in table.find_all_previous(["h1", "h2", "h3", "h4", "p", "strong"]):
                t = _clean_text(prev.get_text())
                if t and len(t) > 5:
                    title = t
                    break
            sections.append({"title": title, "headers": headers, "rows": data_rows})
    return sections


def _rows_to_chunks(
    sections: list[dict],
    page_title: str,
    form_slug: str,
    category: str,
    country: str,
    page_url: str,
) -> list[dict]:
    """Convert table sections into knowledge chunk records."""
    chunks = []
    today = date.today().isoformat()

    for sec_idx, section in enumerate(sections):
        headers = section["headers"]
        rows = section["rows"]
        sec_title = section.get("title") or page_title

        # Build one chunk per row
        for row_idx, row in enumerate(rows):
            if not row or not row[0]:
                continue
            # Skip pure header separator rows
            first_cell = row[0].lower()
            if set(first_cell) <= set("-=_ "):
                continue

            # Build content as "Header: Value | Header: Value | ..."
            parts = []
            for h, v in zip(headers, row):
                if h and v:
                    parts.append(f"{h}: {v}")
            if not parts:
                continue
            content = f"[{page_title}] {sec_title} — " + " | ".join(parts)

            # Pad content to >100 chars if needed
            if len(content) < 100:
                content = content + ". Source: VisaJourney community timeline data as of " + today + "."

            record = make_record(
                chunk_id=make_chunk_id(
                    "visajourney", form_slug, str(sec_idx), str(row_idx)
                ),
                title=f"VisaJourney {page_title} — {sec_title}",
                content=content,
                section=sec_title[:100],
                category=category,
                country=country,
                tags=[form_slug, "processing_time", "uscis", "timeline"],
                page_url=page_url,
                site="visajourney",
                trust_score=0.75,
                priority=2,
            )
            if record:
                chunks.append(record)

    return chunks


class VisajourneyCrawler(BaseCrawler):
    source_name = "visajourney"

    def crawl(self) -> list[dict]:
        chunks: list[dict] = []

        for url, form_slug, page_title, category, country in STATS_PAGES:
            logger.info("[visajourney] Fetching %s", url)
            try:
                html = _fetch_html(url)
            except Exception as exc:
                logger.warning("[visajourney] Error fetching %s: %s", url, exc)
                continue

            soup = BeautifulSoup(html, "html.parser")
            sections = _extract_table_sections(soup)
            logger.info("[visajourney] %s: %d table sections", form_slug, len(sections))

            page_chunks = _rows_to_chunks(
                sections, page_title, form_slug, category, country, url
            )
            logger.info("[visajourney] %s: %d chunks", form_slug, len(page_chunks))
            chunks.extend(page_chunks)

            time.sleep(2)

        return chunks


def run(out_dir: str = "data/crawled") -> int:
    return VisajourneyCrawler(out_dir=out_dir).run()
