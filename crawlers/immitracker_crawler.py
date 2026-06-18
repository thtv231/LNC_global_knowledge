"""myimmitracker.com Canada tracker listing crawler using BeautifulSoup.

Scrapes the public tracker listing pages at myimmitracker.com/ca/trackers
(paginated). Each page shows tracker cards with:
  - Tracker name (e.g. "Consolidated Express Entry PR Application Tracker")
  - Category (e.g. "Permanent Skilled Streams")
  - Case count (e.g. 21462)
  - Last updated (e.g. "about 1 hour ago")
  - Tracker URL slug

Individual case data is JS-rendered and login-protected, so we extract the
publicly visible tracker metadata and turn each tracker into an informative
knowledge chunk describing what the tracker covers and how active it is.

We also scrape the Canada-specific program pages from IRCC for supplementary
context (if accessible without JS).
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

BASE_URL = "https://myimmitracker.com"
TRACKER_LIST_URL = "https://myimmitracker.com/ca/trackers"

# Category → RAG category mapping
_CATEGORY_MAP = {
    "permanent skilled streams": "express_entry",
    "family based/sponsored": "general",
    "family sponsored": "general",
    "": "general",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

_MAX_PAGES = 4  # Listing is paginated; scrape up to this many pages


def _fetch_html(url: str, timeout: int = 20) -> str:
    r = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
    r.raise_for_status()
    return r.text


def _parse_tracker_cards(html: str) -> list[dict]:
    """
    Parse a tracker listing page and return a list of tracker dicts.
    Each dict has keys: name, category, case_count, last_updated, url.
    """
    soup = BeautifulSoup(html, "html.parser")
    trackers = []

    for div in soup.find_all("div", class_="tracker"):
        content = div.find("div", class_="content")
        if not content:
            continue

        # Name
        name_span = content.find("span", class_="name")
        name = name_span.get_text(strip=True) if name_span else ""
        if not name:
            continue

        # Subtracker flag
        is_subtracker = "subtracker" in content.get_text().lower()

        # Category
        cat_span = content.find("span", class_="category")
        category_text = cat_span.get_text(strip=True).lower() if cat_span else ""

        # Case count
        cases_div = content.find("div", class_="cases")
        case_count = ""
        if cases_div:
            spans = cases_div.find_all("span")
            if spans:
                case_count = spans[0].get_text(strip=True)

        # Last updated
        update_div = content.find("div", class_="update")
        last_updated = ""
        if update_div:
            parts = [s.get_text(strip=True) for s in update_div.find_all("span")]
            last_updated = " ".join(parts)

        # URL
        link = content.find("a", href=True)
        tracker_url = (BASE_URL + link["href"]) if link else ""

        trackers.append({
            "name": name,
            "category_text": category_text,
            "case_count": case_count,
            "last_updated": last_updated,
            "url": tracker_url,
            "is_subtracker": is_subtracker,
        })

    return trackers


def _has_next_page(html: str, current_page: int) -> bool:
    """Check if there is a next page in pagination."""
    soup = BeautifulSoup(html, "html.parser")
    pag = soup.find(class_="pagination")
    if not pag:
        return False
    # Look for a link with 'next' text or a page number > current
    for a in pag.find_all("a"):
        txt = a.get_text(strip=True).lower()
        if "next" in txt:
            return True
        try:
            if int(txt) > current_page:
                return True
        except ValueError:
            pass
    return False


def _tracker_to_chunk(tracker: dict, page_url: str) -> dict:
    """Convert a tracker card dict into a knowledge chunk record."""
    name = tracker["name"]
    case_count = tracker["case_count"]
    last_updated = tracker["last_updated"]
    category_text = tracker["category_text"]
    tracker_url = tracker["url"]
    today = date.today().isoformat()

    # Map category
    rag_category = _CATEGORY_MAP.get(category_text, "general")

    # Determine country from name/category
    country = "canada"

    # Build descriptive content
    count_str = f"{case_count} cases" if case_count else "an active community"
    cat_str = category_text.title() if category_text else "Immigration"
    sub_str = " (subtracker)" if tracker["is_subtracker"] else ""

    content = (
        f"MyImmiTracker Canada: {name}{sub_str}. "
        f"Category: {cat_str}. "
        f"This tracker has {count_str} tracked by community members. "
        f"Last updated {last_updated}. "
        f"Tracker URL: {tracker_url}. "
        f"This is a crowd-sourced Canada immigration timeline tracker where applicants "
        f"share their case milestones (submission date, AOR, biometrics, medical, PPR, COPR). "
        f"Data reflects real applicant experiences as of {today}."
    )

    record = make_record(
        chunk_id=make_chunk_id("immitracker", name),
        title=f"MyImmiTracker: {name}",
        content=content,
        section="tracker_listing",
        category=rag_category,
        country=country,
        tags=["immitracker", "canada", category_text, "processing_time", "tracker"],
        page_url=tracker_url or page_url,
        site="myimmitracker",
        trust_score=0.70,
        priority=2,
    )
    return record


class ImmiTrackerCrawler(BaseCrawler):
    source_name = "immitracker"

    def crawl(self) -> list[dict]:
        chunks: list[dict] = []
        seen_names: set[str] = set()

        for page_num in range(1, _MAX_PAGES + 1):
            page_url = (
                TRACKER_LIST_URL
                if page_num == 1
                else f"{TRACKER_LIST_URL}?page={page_num}"
            )
            logger.info("[immitracker] Fetching page %d: %s", page_num, page_url)

            try:
                html = _fetch_html(page_url)
            except Exception as exc:
                logger.warning("[immitracker] Error fetching %s: %s", page_url, exc)
                break

            trackers = _parse_tracker_cards(html)
            logger.info(
                "[immitracker] Page %d: %d trackers found", page_num, len(trackers)
            )

            if not trackers:
                break

            for tracker in trackers:
                name = tracker["name"]
                if name in seen_names:
                    continue
                seen_names.add(name)

                record = _tracker_to_chunk(tracker, page_url)
                if record:
                    chunks.append(record)

            if not _has_next_page(html, page_num):
                logger.info("[immitracker] No more pages after page %d.", page_num)
                break

            time.sleep(2)

        logger.info("[immitracker] Total chunks: %d", len(chunks))
        return chunks


def run(out_dir: str = "data/crawled") -> int:
    return ImmiTrackerCrawler(out_dir=out_dir).run()
