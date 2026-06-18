"""US Visa Bulletin scraper (replaces Trackitt which blocks headless browsers).

Scrapes the monthly Visa Bulletins from travel.state.gov — a public US government
site with no bot protection. Extracts:
  - Family-Sponsored Final Action Dates (Table A)
  - Employment-Based Final Action Dates (Table C)
  - Dates for Filing (Tables B & D)
  - Diversity Visa (DV) cutoff numbers

Each bulletin section becomes a knowledge chunk. We scrape the 3 most recent
bulletins (current fiscal year) to give the RAG pipeline recent + historical context.
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

BASE_URL = "https://travel.state.gov"
BULLETIN_INDEX = (
    "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Maximum number of recent bulletins to scrape
_MAX_BULLETINS = 3


def _fetch_html(url: str, timeout: int = 25) -> str:
    r = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
    r.raise_for_status()
    return r.text


def _get_recent_bulletin_urls(index_html: str) -> list[tuple[str, str]]:
    """
    Parse the bulletin index page and return the _MAX_BULLETINS most recent
    bulletin URLs with their display names.
    Returns list of (url, name) tuples.
    """
    soup = BeautifulSoup(index_html, "html.parser")
    seen_urls: set[str] = set()
    results: list[tuple[str, str]] = []

    # Bulletins appear as links containing 'visa-bulletin-for-'
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "visa-bulletin-for-" not in href:
            continue
        full_url = href if href.startswith("http") else BASE_URL + href
        if full_url in seen_urls:
            continue

        name = re.sub(r"\s+", " ", a.get_text(separator=" ", strip=True))
        # Skip abbreviated nav text like "June2026" (no space, < 15 chars)
        if len(name) < 15 or " " not in name:
            # derive name from URL instead
            m = re.search(r"visa-bulletin-for-(.+?)(?:\.html)?$", href)
            if m:
                name = m.group(1).replace("-", " ").title()
            else:
                name = full_url.split("/")[-1].replace(".html", "").replace("-", " ").title()

        seen_urls.add(full_url)
        results.append((full_url, name))
        if len(results) >= _MAX_BULLETINS:
            break

    return results


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


# Table label patterns that identify each section
_TABLE_LABELS = {
    "family_final_action": re.compile(r"family.?sponsored.*final.?action", re.I),
    "family_filing_dates": re.compile(r"family.?sponsored.*filing", re.I),
    "employment_final_action": re.compile(r"employment.?based.*final.?action", re.I),
    "employment_filing_dates": re.compile(r"employment.?based.*filing", re.I),
    "diversity_visa": re.compile(r"diversity.*visa|dv.*cutoff", re.I),
}


def _label_table(preceding_text: str) -> str:
    """Classify a table by the heading text that precedes it."""
    for label, pat in _TABLE_LABELS.items():
        if pat.search(preceding_text):
            return label
    return "other"


def _table_to_text(table_tag) -> tuple[str, list[str]]:
    """
    Convert an HTML table to (header_text, data_rows_as_strings).
    Returns (combined_headers, list_of_row_strings).
    """
    rows = table_tag.find_all("tr")
    if not rows:
        return "", []

    headers = [_clean(c.get_text()) for c in rows[0].find_all(["th", "td"])]
    header_str = " | ".join(h for h in headers if h)

    data_strings = []
    for row in rows[1:]:
        cells = [_clean(c.get_text()) for c in row.find_all(["td", "th"])]
        if not any(cells):
            continue
        # Build "Category: val1 | Country: val2 | ..."
        parts = []
        for h, v in zip(headers, cells):
            if v:
                label = h if h else "Value"
                parts.append(f"{label}: {v}")
        if parts:
            data_strings.append(" | ".join(parts))

    return header_str, data_strings


def _bulletin_to_chunks(
    html: str,
    bulletin_name: str,
    bulletin_url: str,
) -> list[dict]:
    """Parse a single visa bulletin page and return knowledge chunks."""
    soup = BeautifulSoup(html, "html.parser")
    chunks = []
    today = date.today().isoformat()

    tables = soup.find_all("table")
    for t_idx, table in enumerate(tables):
        # Find preceding heading to classify the table
        heading = ""
        for prev in table.find_all_previous(["h1", "h2", "h3", "h4", "strong", "b"]):
            txt = _clean(prev.get_text())
            if txt and len(txt) > 3:
                heading = txt
                break

        label = _label_table(heading)
        if label == "other" and not heading:
            continue

        header_str, data_rows = _table_to_text(table)
        if not data_rows:
            continue

        section_name = heading or label.replace("_", " ").title()

        # Build one chunk per row (each row = one preference category)
        for row_idx, row_str in enumerate(data_rows):
            content = (
                f"US Visa Bulletin {bulletin_name} — {section_name}: {row_str}. "
                f"Source: US Department of State, travel.state.gov, retrieved {today}."
            )
            record = make_record(
                chunk_id=make_chunk_id(
                    "visabulletin", bulletin_name, label, str(t_idx), str(row_idx)
                ),
                title=f"US Visa Bulletin {bulletin_name} — {section_name}",
                content=content,
                section=section_name[:100],
                category=(
                    "eb2_niw"
                    if "employment" in label
                    else "general" if "diversity" in label
                    else "general"
                ),
                country="usa",
                tags=[
                    "visa_bulletin",
                    label,
                    "priority_dates",
                    "uscis",
                    bulletin_name.lower().replace(" ", "_"),
                ],
                page_url=bulletin_url,
                site="travel.state.gov",
                trust_score=0.95,
                priority=1,
            )
            if record:
                chunks.append(record)

    return chunks


class TrackittCrawler(BaseCrawler):
    """
    Replacement for the original Trackitt crawler (trackitt.com blocks all bots).
    Now scrapes the US Visa Bulletin from travel.state.gov instead.
    The source_name remains 'trackitt' to avoid renaming the output directory.
    """

    source_name = "trackitt"

    def crawl(self) -> list[dict]:
        chunks: list[dict] = []

        logger.info("[visabulletin] Fetching bulletin index from %s", BULLETIN_INDEX)
        try:
            index_html = _fetch_html(BULLETIN_INDEX)
        except Exception as exc:
            logger.error("[visabulletin] Cannot fetch index: %s", exc)
            return chunks

        bulletin_urls = _get_recent_bulletin_urls(index_html)
        if not bulletin_urls:
            logger.warning("[visabulletin] No bulletin URLs found on index page.")
            return chunks

        logger.info(
            "[visabulletin] Found %d recent bulletins: %s",
            len(bulletin_urls),
            [name for _, name in bulletin_urls],
        )

        for url, name in bulletin_urls:
            logger.info("[visabulletin] Fetching bulletin: %s (%s)", name, url)
            try:
                html = _fetch_html(url)
            except Exception as exc:
                logger.warning("[visabulletin] Error fetching %s: %s", url, exc)
                continue

            bulletin_chunks = _bulletin_to_chunks(html, name, url)
            logger.info(
                "[visabulletin] %s: %d chunks", name, len(bulletin_chunks)
            )
            chunks.extend(bulletin_chunks)
            time.sleep(2)

        return chunks


def run(out_dir: str = "data/crawled") -> int:
    return TrackittCrawler(out_dir=out_dir).run()
