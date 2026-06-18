"""WeGreened "success-stories" crawler.

Separate Strapi collection from the one `wegreened_crawler.py` already
covers (`latest-informations` + the L-1 visa FAQ page). Confirmed live via
direct query on 2026-06-16:

    GET https://cms.wegreened.com/api/success-stories
    -> meta.pagination.total == 7533

This single collection backs BOTH the narrative case-study posts rendered
at wegreened.com/blog/<category>/<slug> (NIW / EB-1 / O-1 approvals with a
client testimonial) AND the recurring "Daily Approval Summary" digest posts
that bundle several cases published the same day. The two are told apart
by `blog_categories[].slug == "daily-approval-summary"` — no LLM step
needed, every record already carries structured taxonomy:
`blog_categories` (visa category + research field), `blog_tags`,
`blog_country` (applicant's country), `client_field`, `client_position`,
`blog_citation_range`, and a ready-to-use relative `canonical` URL.

Sorted newest-first (`sort=publishedDate:desc`). Each page is saved to disk
immediately (via `BaseCrawler.save()`, which already tracks `seen_ids.json`)
rather than accumulated and written once at the end -- the CMS API is flaky
enough in practice (observed ReadTimeouts requiring 2-3 retries per page,
~100s with `populate=*`) that a ~76-page backfill could plausibly get killed
partway through, and nothing fetched so far should be lost when that happens.

A small `_state.json` (newest chunk_id seen as of the last run that reached
the end of its walk) lets later runs stop as soon as they hit that
high-water mark instead of re-walking the whole backlog -- this is *not*
the same as "this page had zero new records", which is also true mid-way
through a crash-resumed backfill and would stop far too early.
"""
from __future__ import annotations
import json
import logging
import time

import httpx

from crawlers.base import BaseCrawler, make_chunk_id, make_record
from crawlers.wegreened_crawler import HEADERS, SITE_BASE, html_to_text

logger = logging.getLogger(__name__)

API_URL = "https://cms.wegreened.com/api/success-stories"

# wegreened_crawler.py's shared `_get_json` retries at a 30s per-attempt
# timeout, which this endpoint's paginated+populated responses routinely
# exceed even when the server is about to succeed (observed repeatedly on
# 2026-06-16: every attempt that failed was a ReadTimeout, never a 4xx/5xx).
# A longer single-attempt timeout converts most of those into one slower
# success instead of 2-3 guaranteed-to-fail retries. Kept local rather than
# changing the shared helper, which `wegreened_crawler.py`'s lighter
# `latest-informations` calls don't need.
_TIMEOUT_S = 75
_RETRY_DELAYS = (5, 15, 30)


def _get_json(url: str, params: dict) -> dict | None:
    for attempt, delay in enumerate((0, *_RETRY_DELAYS)):
        if delay:
            time.sleep(delay)
        try:
            r = httpx.get(url, params=params, headers=HEADERS, timeout=_TIMEOUT_S)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.warning(
                "[wegreened_success_stories] request failed (attempt %d) for %s %s: %s",
                attempt + 1, url, params, exc,
            )
    logger.error("[wegreened_success_stories] giving up on %s %s after %d attempts", url, params, len(_RETRY_DELAYS) + 1)
    return None

# Only the relations _story_to_chunk() actually reads -- `populate=*` also
# pulls seo/thumbnail/localizations/blog_next_post/blog_previous_post, which
# are unused here and were the likely cause of the ReadTimeouts observed at
# pageSize=100 (first live backfill attempt, 2026-06-16, took >5 min/page).
_POPULATE_FIELDS = ["blog_categories", "blog_tags", "blog_country", "blog_citation_range"]

_PAGE_SIZE = 50
_MAX_PAGES = 200  # safety cap; backlog is ~151 pages at _PAGE_SIZE=50 today
_REQUEST_PAUSE = 2  # seconds between pages, same courtesy as wegreened_crawler.py

# blog_categories[].slug -> our category bucket. Everything else in
# blog_categories (the ~380-entry research-field taxonomy) becomes a tag.
_CATEGORY_SLUG_MAP = {
    "niw": "eb2_niw",
    "eb1-green-card": "eb1",
    "success-stories-o1-a": "o1",
}
_DIGEST_SLUG = "daily-approval-summary"

# fallback keyword scan over the title when blog_categories doesn't carry
# an explicit visa-category slug (older records are inconsistently tagged)
_TITLE_KEYWORDS = {
    "niw": "eb2_niw", "national interest waiver": "eb2_niw",
    "eb-1a": "eb1", "eb1a": "eb1", "eb-1b": "eb1", "eb1b": "eb1",
    "eb-1c": "eb1", "eb1c": "eb1", "eb-1": "eb1",
    "o-1a": "o1", "o-1": "o1", "o1 ": "o1",
}


def _classify(blog_categories: list[dict], title: str) -> tuple[str, bool]:
    """Returns (category, is_digest)."""
    slugs = [c.get("slug", "") for c in blog_categories]
    is_digest = _DIGEST_SLUG in slugs

    for slug, category in _CATEGORY_SLUG_MAP.items():
        if slug in slugs:
            return category, is_digest

    title_l = title.lower()
    for kw, category in _TITLE_KEYWORDS.items():
        if kw in title_l:
            return category, is_digest

    return "general", is_digest


def _story_to_chunk(item: dict) -> dict:
    slug = item.get("slug", "")
    title = item.get("title", "")
    content = html_to_text(item.get("content", ""))
    blog_categories = item.get("blog_categories") or []
    category, is_digest = _classify(blog_categories, title)

    field_tags = [c.get("name", "") for c in blog_categories if c.get("slug") not in _CATEGORY_SLUG_MAP and c.get("slug") != _DIGEST_SLUG]
    topic_tags = [t.get("name", "") for t in (item.get("blog_tags") or [])]
    client_field = item.get("client_field") or ""
    applicant_country = (item.get("blog_country") or {}).get("name") or ""
    citation_range = (item.get("blog_citation_range") or {}).get("name") or ""

    tags = ["wegreened", "success_story"]
    tags.extend(t for t in (field_tags + topic_tags + [client_field, applicant_country]) if t)

    # `canonical` is null on most "daily-approval-summary" digest records even
    # though the live site serves them under that category segment (confirmed
    # against the public RSS feed) -- reconstruct it in that case.
    if item.get("canonical"):
        canonical = item["canonical"]
    elif is_digest:
        canonical = f"/blog/{_DIGEST_SLUG}/{slug}/"
    else:
        canonical = f"/blog/{slug}/"
    page_url = f"{SITE_BASE}{canonical}"

    return make_record(
        chunk_id=make_chunk_id("wegreened", "success_story", slug or str(item.get("id", ""))),
        title=title,
        content=content,
        section="draw_result" if is_digest else "success_story",
        category=category,
        country="usa",  # jurisdiction of the program, not the applicant's nationality
        tags=tags[:15],
        page_url=page_url,
        site="wegreened",
        trust_score=0.8,  # firm-verified outcome, not a primary gov source
        priority=1,
        language=item.get("locale", "en"),
        extra={
            "published_date": item.get("publishedDate", ""),
            "client_field": client_field,
            "client_position": item.get("client_position") or "",
            "applicant_country": applicant_country,
            "citation_range": citation_range,
        },
    )


def _fetch_page(page: int) -> dict | None:
    params = {
        "pagination[page]": page,
        "pagination[pageSize]": _PAGE_SIZE,
        "sort": "publishedDate:desc",
    }
    for i, field in enumerate(_POPULATE_FIELDS):
        params[f"populate[{i}]"] = field
    return _get_json(API_URL, params)


class WegreenedSuccessStoriesCrawler(BaseCrawler):
    source_name = "wegreened_success_stories"

    def __init__(self, out_dir: str = "data/crawled") -> None:
        super().__init__(out_dir=out_dir)
        self._state_file = self.out_dir / "_state.json"

    def _load_state(self) -> dict:
        if self._state_file.exists():
            try:
                return json.loads(self._state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_state(self, state: dict) -> None:
        self._state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    def crawl(self) -> list[dict]:
        raise NotImplementedError("WegreenedSuccessStoriesCrawler saves incrementally -- use run(), not crawl()+save()")

    def run(self) -> int:
        logger.info("[%s] Starting crawl...", self.source_name)
        state = self._load_state()
        high_water_mark = state.get("newest_chunk_id")
        # `last_completed_page` is only meaningful while a backfill is still
        # in progress (no high_water_mark yet) -- it lets a run that got
        # killed/interrupted resume past pages it already fetched and saved,
        # instead of re-spending ~1 min/page re-walking from page 1 every
        # time. Any overlap from resuming is harmless since save() dedups
        # by chunk_id regardless.
        page = state.get("last_completed_page", 0) + 1 if high_water_mark is None else 1
        newest_chunk_id: str | None = None
        total_new = 0
        page_count = None
        reached_mark = False
        if page > 1:
            logger.info("[%s] resuming from page %d", self.source_name, page)

        while page <= _MAX_PAGES and (page_count is None or page <= page_count):
            data = _fetch_page(page)
            if data is None:
                logger.warning("[%s] page %d failed, stopping", self.source_name, page)
                break

            items = data.get("data", [])
            meta = data.get("meta", {}).get("pagination", {})
            page_count = meta.get("pageCount", page)
            logger.info("[%s] page %d/%s: %d items", self.source_name, page, page_count, len(items))

            if not items:
                break

            # make_record() returns {} for sub-100-char content -- drop those
            # before indexing into structured_data below.
            page_chunks = [c for c in (_story_to_chunk(item) for item in items) if c]
            if not page_chunks:
                page += 1
                time.sleep(_REQUEST_PAUSE)
                continue
            if newest_chunk_id is None:
                newest_chunk_id = page_chunks[0]["structured_data"]["chunk_id"]

            if high_water_mark is not None:
                marked_idx = next(
                    (i for i, c in enumerate(page_chunks) if c["structured_data"]["chunk_id"] == high_water_mark),
                    None,
                )
                if marked_idx is not None:
                    page_chunks = page_chunks[:marked_idx]
                    reached_mark = True

            total_new += self.save(page_chunks)
            if reached_mark:
                logger.info("[%s] reached previous high-water mark on page %d, stopping", self.source_name, page)
                break

            if high_water_mark is None:
                self._save_state({"last_completed_page": page})

            page += 1
            time.sleep(_REQUEST_PAUSE)

        if newest_chunk_id:
            # backlog fully walked (or caught up to the previous mark) --
            # `last_completed_page` is no longer needed once we have a mark.
            self._save_state({"newest_chunk_id": newest_chunk_id})
        return total_new


def run(out_dir: str = "data/crawled") -> int:
    return WegreenedSuccessStoriesCrawler(out_dir=out_dir).run()
