"""RSS feed crawler for CIC News, Moving2Canada, Webber Immigration."""
from __future__ import annotations
import logging
import time

import feedparser
import httpx
from bs4 import BeautifulSoup

from crawlers.base import make_chunk_id, make_record

logger = logging.getLogger(__name__)

# ILW removed — all feed URLs return 404 as of 2026-06-16
RSS_SOURCES = [
    {
        "name": "cicnews",
        "url": "https://www.cicnews.com/feed",
        "country": "canada",
        "category": "general",
        "section": "policy_update",
        "trust_score": 0.85,
        "priority": 1,
        "language": "en",
    },
    {
        "name": "moving2canada",
        "url": "https://moving2canada.com/feed/",
        "country": "canada",
        "category": "general",
        "section": "policy_update",
        "trust_score": 0.80,
        "priority": 1,
        "language": "en",
    },
    {
        "name": "webber",
        "url": "https://webberimmigration.substack.com/feed",
        "country": "usa",
        "category": "eb2_niw",
        "section": "case_timeline",
        "trust_score": 0.85,
        "priority": 1,
        "language": "en",
    },
]

SOURCE_MAP: dict[str, dict] = {s["name"]: s for s in RSS_SOURCES}


def _extract_text(entry) -> str:
    if hasattr(entry, "content") and entry.content:
        html = entry.content[0].value
        text = BeautifulSoup(html, "html.parser").get_text(separator="\n").strip()
        if len(text) >= 100:
            return text
    if hasattr(entry, "summary") and entry.summary:
        text = BeautifulSoup(entry.summary, "html.parser").get_text().strip()
        if len(text) >= 100:
            return text
    # Fallback: fetch full article via crawl4ai (handles JS-rendered sites)
    link = entry.get("link") or entry.get("id") or ""
    if link:
        try:
            import asyncio
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig

            async def _get():
                cfg = CrawlerRunConfig(wait_until="networkidle", page_timeout=20000, delay_before_return_html=1.5)
                async with AsyncWebCrawler(config=BrowserConfig(headless=True, verbose=False)) as c:
                    res = await c.arun(url=link, config=cfg)
                    return res.markdown or ""

            text = asyncio.run(_get()).strip()
            if len(text) >= 100:
                return text[:5000]
        except Exception as exc:
            logger.debug("crawl4ai article fetch failed for %s: %s", link, exc)
    return entry.get("title", "")


_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _fetch_feed(url: str):
    """Fetch RSS via httpx with browser UA, fallback to feedparser direct."""
    try:
        r = httpx.get(url, headers=_HEADERS, timeout=15, follow_redirects=True)
        if r.status_code == 200 and r.text:
            return feedparser.parse(r.text)
    except Exception as exc:
        logger.debug("[rss] httpx fetch failed for %s: %s", url, exc)
    return feedparser.parse(url)


def crawl_source(source: dict) -> list[dict]:
    logger.info("[rss/%s] Fetching %s", source["name"], source["url"])
    try:
        feed = _fetch_feed(source["url"])
    except Exception as exc:
        logger.warning("[rss/%s] Parse error: %s", source["name"], exc)
        return []

    chunks = []
    for entry in feed.entries:
        url = entry.get("link") or entry.get("id") or ""
        content = _extract_text(entry)
        tags = [t.term for t in entry.get("tags", []) if hasattr(t, "term")]
        record = make_record(
            chunk_id=make_chunk_id("rss", source["name"], url),
            title=entry.get("title", ""),
            content=content,
            section=source["section"],
            category=source["category"],
            country=source["country"],
            tags=tags,
            page_url=url,
            site=source["name"],
            trust_score=source["trust_score"],
            priority=source["priority"],
            language=source["language"],
            extra={
                "published": entry.get("published", ""),
                "author": entry.get("author", ""),
            },
        )
        if record:
            chunks.append(record)

    logger.info("[rss/%s] %d items parsed", source["name"], len(chunks))
    return chunks


def run(sources: list[str] | None = None, out_dir: str = "data/crawled") -> dict[str, int]:
    """Crawl RSS sources and save. Returns {source_name: new_chunk_count}."""
    from crawlers.base import BaseCrawler

    targets = [SOURCE_MAP[n] for n in sources if n in SOURCE_MAP] if sources else RSS_SOURCES
    results: dict[str, int] = {}

    for source in targets:
        chunks = crawl_source(source)

        class _RssSrc(BaseCrawler):
            source_name = source["name"]

            def crawl(self):
                return chunks

        saved = _RssSrc(out_dir=out_dir).run()
        results[source["name"]] = saved
        time.sleep(1)

    return results
