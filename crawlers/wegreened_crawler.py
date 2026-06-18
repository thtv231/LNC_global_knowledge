"""WeGreened (North America Immigration Law Group / Chen Immigration) crawler.

wegreened.com is a Nuxt.js SSR site backed by a public, unauthenticated
Strapi CMS REST API at https://cms.wegreened.com/api. Two content types are
harvested here:

  1. latest-informations — the firm's "Latest Information" news feed,
     mostly EB1A/EB1B/EB2-NIW/O1 approval-count announcements. Paginated;
     a full historical backfill is done via pagination[page]/pagination[pageSize].
  2. pages (filtered to the L-1 visa FAQ page) — a static service page whose
     FAQ content is exposed structured (question/answer pairs) via the
     page's seo.structuredData.mainEntity (schema.org FAQPage JSON-LD), so it
     can be pulled as clean JSON instead of scraping rendered HTML.

The CMS API is flaky under load (observed ReadTimeouts on otherwise-valid
requests), so all calls go through a small retry-with-backoff wrapper.
"""
from __future__ import annotations
import logging
import time

import httpx
from bs4 import BeautifulSoup

from crawlers.base import BaseCrawler, make_chunk_id, make_record

logger = logging.getLogger(__name__)

API_BASE = "https://cms.wegreened.com/api"
NEWS_URL = f"{API_BASE}/latest-informations"
PAGES_URL = f"{API_BASE}/pages"
SITE_BASE = "https://www.wegreened.com"

L1_VISA_SLUG = "L-Visa-Intracompany-Transferee-Visa"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_NEWS_PAGE_SIZE = 100
_MAX_PAGES = 10  # safety cap; 216 items / 100 per page ~= 3 pages today
_RETRY_DELAYS = (5, 15, 30)

_VISA_KEYWORDS = ["eb1a", "eb1b", "eb1c", "niw", "o1", "i-140", "i-485", "perm"]


def _get_json(url: str, params: dict) -> dict | None:
    for attempt, delay in enumerate((0, *_RETRY_DELAYS)):
        if delay:
            time.sleep(delay)
        try:
            r = httpx.get(url, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.warning(
                "[wegreened] request failed (attempt %d) for %s %s: %s",
                attempt + 1, url, params, exc,
            )
    logger.error("[wegreened] giving up on %s %s after %d attempts", url, params, len(_RETRY_DELAYS) + 1)
    return None


def html_to_text(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text(separator="\n").strip()


def _detect_tags(title: str) -> list[str]:
    title_l = title.lower()
    return [kw for kw in _VISA_KEYWORDS if kw in title_l]


def fetch_all_news_articles() -> list[dict]:
    """Paginate the latest-informations API and return raw API items (un-chunked)."""
    articles: list[dict] = []
    page = 1
    page_count = None

    while page <= _MAX_PAGES and (page_count is None or page <= page_count):
        params = {
            "pagination[page]": page,
            "pagination[pageSize]": _NEWS_PAGE_SIZE,
        }
        data = _get_json(NEWS_URL, params)
        if data is None:
            logger.warning("[wegreened] news page %d failed, stopping pagination", page)
            break

        items = data.get("data", [])
        meta = data.get("meta", {}).get("pagination", {})
        page_count = meta.get("pageCount", page)
        logger.info("[wegreened] news page %d/%s: %d items", page, page_count, len(items))

        articles.extend(items)
        if not items:
            break
        page += 1
        time.sleep(2)

    return articles


def _news_item_to_chunk(item: dict) -> dict:
    slug = item.get("slug", "")
    title = item.get("title", "")
    content = html_to_text(item.get("content", ""))
    page_url = f"{SITE_BASE}/Latest-Information/{slug}" if slug else ""

    return make_record(
        chunk_id=make_chunk_id("wegreened", "news", slug or str(item.get("id", ""))),
        title=title,
        content=content,
        section="approvals",
        category="General",
        country="usa",
        tags=["wegreened", "approvals"] + _detect_tags(title),
        page_url=page_url,
        site="wegreened",
        trust_score=0.75,
        priority=2,
        language=item.get("locale", "en"),
        extra={
            "published_date": item.get("publishedDate", ""),
            "author": item.get("author", ""),
        },
    )


def _crawl_news() -> list[dict]:
    articles = fetch_all_news_articles()
    chunks = [c for item in articles if (c := _news_item_to_chunk(item))]
    logger.info("[wegreened] news total chunks: %d", len(chunks))
    return chunks


def _l1_visa_faq_to_chunks(faqs: list[dict]) -> list[dict]:
    page_url = f"{SITE_BASE}/{L1_VISA_SLUG}"
    chunks: list[dict] = []

    for idx, faq in enumerate(faqs):
        question = faq.get("name", "")
        answer_html = faq.get("acceptedAnswer", {}).get("text", "")
        answer = html_to_text(answer_html)
        if not question or not answer:
            continue

        record = make_record(
            chunk_id=make_chunk_id("wegreened", "l1_visa_faq", str(idx), question),
            title=f"L-1 Visa FAQ: {question}",
            content=f"Q: {question}\n\nA: {answer}",
            section="faq",
            category="L1-Visa",
            country="usa",
            tags=["wegreened", "l1_visa", "l-1a", "l-1b", "intracompany_transferee", "faq"],
            page_url=page_url,
            site="wegreened",
            trust_score=0.80,
            priority=1,
        )
        if record:
            chunks.append(record)

    return chunks


def _crawl_l1_visa_faq() -> list[dict]:
    data = _get_json(PAGES_URL, {"filters[slug][$eq]": L1_VISA_SLUG, "populate": "*"})
    if not data or not data.get("data"):
        logger.warning("[wegreened] L-1 visa FAQ page fetch failed or empty")
        return []

    page = data["data"][0]
    faqs = page.get("seo", {}).get("structuredData", {}).get("mainEntity", [])
    chunks = _l1_visa_faq_to_chunks(faqs)
    logger.info("[wegreened] L-1 visa FAQ chunks: %d", len(chunks))
    return chunks


class WegreenedCrawler(BaseCrawler):
    source_name = "wegreened"

    def crawl(self) -> list[dict]:
        chunks = _crawl_news()
        chunks.extend(_crawl_l1_visa_faq())
        return chunks


def run(out_dir: str = "data/crawled") -> int:
    return WegreenedCrawler(out_dir=out_dir).run()
