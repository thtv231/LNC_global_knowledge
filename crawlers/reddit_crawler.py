"""Reddit crawler — uses crawl4ai stealth browser to call Reddit JSON API."""
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta

from crawlers.base import BaseCrawler, make_chunk_id, make_record

logger = logging.getLogger(__name__)

REDDIT_SOURCES = [
    # Canada
    {"subreddit": "ExpressEntry",      "country": "canada",      "category": "express_entry",  "min_score": 5,  "limit": 50, "top_n_comments": 5},
    {"subreddit": "ImmigrationCanada", "country": "canada",      "category": "general",         "min_score": 10, "limit": 50, "top_n_comments": 3},
    {"subreddit": "CanadaVisa",        "country": "canada",      "category": "general",         "min_score": 5,  "limit": 50, "top_n_comments": 3},
    {"subreddit": "PNP",               "country": "canada",      "category": "pnp",             "min_score": 3,  "limit": 30, "top_n_comments": 3},
    # USA
    {"subreddit": "USCIS",             "country": "usa",         "category": "general",         "min_score": 10, "limit": 50, "top_n_comments": 5},
    {"subreddit": "immigration",       "country": "usa",         "category": "general",         "min_score": 15, "limit": 50, "top_n_comments": 0},
    {"subreddit": "EB2NIW",            "country": "usa",         "category": "eb2_niw",         "min_score": 1,  "limit": 50, "top_n_comments": 5},
    # New Zealand
    {"subreddit": "NZImmigration",     "country": "new_zealand", "category": "skilled_migrant", "min_score": 3,  "limit": 30, "top_n_comments": 3},
]

_CUTOFF_DAYS = 180   # 6 months — wider window to capture active but slow subreddits


_JS_FETCH = """
async () => {
    const url = arguments[0];
    try {
        const r = await fetch(url, {
            headers: {
                'Accept': 'application/json',
                'User-Agent': navigator.userAgent
            },
            credentials: 'include'
        });
        return await r.text();
    } catch(e) {
        return '';
    }
}
"""


async def _fetch_json_via_browser(url: str) -> dict | list | None:
    """Fetch a Reddit .json URL from inside a stealth Chromium instance."""
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
    from crawl4ai.async_configs import CrawlerRunConfig

    browser_cfg = BrowserConfig(headless=True, verbose=False, use_managed_browser=False)

    # First visit reddit.com to get cookies, then fetch JSON
    js_script = f"""
(async () => {{
    const r = await fetch('{url}', {{
        headers: {{ 'Accept': 'application/json' }},
        credentials: 'include'
    }});
    return await r.text();
}})()
"""
    run_cfg = CrawlerRunConfig(
        url=f"https://www.reddit.com/r/{url.split('/r/')[1].split('/')[0]}/",
        js_code=js_script,
        wait_until="networkidle",
        page_timeout=30000,
        delay_before_return_html=2,
    )

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=f"https://www.reddit.com/r/{url.split('/r/')[1].split('/')[0]}/", config=run_cfg)
        # js_code result is in result.js_code_result or we parse from html
        js_result = getattr(result, "js_code_result", None)
        if js_result:
            try:
                return json.loads(js_result)
            except Exception:
                pass
        return None


async def _fetch_subreddit_json(subreddit: str, limit: int = 100) -> list[dict]:
    """Try multiple methods to get subreddit JSON data."""
    import httpx

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    # Method 1: Direct JSON API with browser UA
    url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={min(limit, 100)}&raw_json=1"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                data = r.json()
                posts = data.get("data", {}).get("children", [])
                logger.info("[reddit] r/%s: %d posts via JSON API", subreddit, len(posts))
                return [p["data"] for p in posts if p.get("kind") == "t3"]
    except Exception as exc:
        logger.debug("[reddit] JSON API failed for r/%s: %s", subreddit, exc)

    # Method 2: RSS feed via feedparser
    try:
        import feedparser
        await asyncio.sleep(2)  # back off before retry
        feed = feedparser.parse(
            f"https://www.reddit.com/r/{subreddit}/new.rss?limit=100",
            request_headers={"User-Agent": headers["User-Agent"]},
        )
        if feed.entries:
            logger.info("[reddit] r/%s: %d entries via RSS", subreddit, len(feed.entries))
            posts = []
            for e in feed.entries:
                link = e.get("link", "")
                post_id = link.rstrip("/").split("/")[-2] if "/comments/" in link else ""
                posts.append({
                    "id": post_id,
                    "title": e.get("title", ""),
                    "selftext": "",
                    "score": 0,
                    "link_flair_text": "",
                    "permalink": link.replace("https://www.reddit.com", ""),
                    "created_utc": e.get("published_parsed") and
                                   datetime(*e.published_parsed[:6], tzinfo=timezone.utc).timestamp() or 0,
                    "num_comments": 0,
                    "author": e.get("author", ""),
                })
            return posts
    except Exception as exc:
        logger.debug("[reddit] RSS failed for r/%s: %s", subreddit, exc)

    logger.warning("[reddit] r/%s: all fetch methods failed", subreddit)
    return []


_COMMENTS_JS = """
let found = 0;
for (let i = 0; i < 16; i++) {
    found = document.querySelectorAll('shreddit-comment').length;
    const post = document.querySelector('shreddit-post');
    if (found > 0 && post) break;
    window.scrollBy(0, 600);
    await new Promise(r => setTimeout(r, 500));
}
const post = document.querySelector('shreddit-post');
let selftext = '';
if (post) {
    const bodyEl = post.querySelector('[slot="text-body"]') || post.querySelector('.md');
    selftext = bodyEl ? bodyEl.innerText : '';
}
const els = Array.from(document.querySelectorAll('shreddit-comment'));
const comments = els.map(el => {
    const bodyEl = el.querySelector('[slot="comment"]') || el.querySelector('.md');
    return {
        author: el.getAttribute('author') || '',
        score: parseInt(el.getAttribute('score') || '0', 10),
        depth: el.getAttribute('depth') || '',
        text: bodyEl ? bodyEl.innerText : ''
    };
});
return JSON.stringify({selftext: selftext, comments: comments});
"""


async def _fetch_post_comments(
    subreddit: str, post_id: str, top_n: int, crawler=None,
) -> tuple[str, list[str]]:
    """Fetch post body and top comments by rendering the post in a real browser
    (crawl4ai) and reading the hydrated <shreddit-post>/<shreddit-comment>
    web components. Reddit's JSON API and old.reddit.com both 403 without auth,
    but the rendered web app works fine for a real browser session.
    """
    if not post_id:
        return "", []

    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig

    url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}/"
    run_cfg = CrawlerRunConfig(
        wait_until="domcontentloaded",
        page_timeout=40000,
        js_code=_COMMENTS_JS,
    )

    async def _run(c) -> tuple[str, list[str]]:
        result = await c.arun(url=url, config=run_cfg)
        js_res = getattr(result, "js_execution_result", None)
        if not js_res or not js_res.get("results"):
            return "", []
        raw = js_res["results"][0]
        if not isinstance(raw, str):
            return "", []
        data = json.loads(raw)
        selftext = data.get("selftext", "") or ""
        if selftext in ("[deleted]", "[removed]"):
            selftext = ""
        comments = sorted(data.get("comments", []), key=lambda c: c.get("score", 0), reverse=True)
        bodies = [
            c["text"] for c in comments
            if c.get("text") and c["text"] not in ("[deleted]", "[removed]")
        ][:top_n]
        return selftext, bodies

    try:
        if crawler is not None:
            return await _run(crawler)
        browser_cfg = BrowserConfig(headless=True, verbose=False)
        async with AsyncWebCrawler(config=browser_cfg) as crawler_:
            return await _run(crawler_)
    except Exception as exc:
        logger.debug("[reddit] Comment fetch failed for %s/%s: %s", subreddit, post_id, exc)
        return "", []



def _build_content(title: str, selftext: str, comments: list[str]) -> str:
    parts = [title]
    if selftext and len(selftext) > 20:
        parts.append(selftext[:3000])
    if comments:
        parts.append("Community responses:")
        parts.extend(f"- {c[:500]}" for c in comments)
    return "\n\n".join(parts)


async def crawl_subreddit_async(config: dict, crawler=None) -> list[dict]:
    subreddit = config["subreddit"]
    cutoff_ts = (datetime.now(tz=timezone.utc) - timedelta(days=_CUTOFF_DAYS)).timestamp()

    raw_posts = await _fetch_subreddit_json(subreddit, config["limit"])
    if not raw_posts:
        return []

    # RSS fallback returns score=0 for all posts; skip score filter in that case
    scores_available = any(p.get("score", 0) != 0 for p in raw_posts)

    chunks: list[dict] = []
    for post in raw_posts:
        score = post.get("score", 0)
        if scores_available and score < config["min_score"]:
            continue
        created_utc = post.get("created_utc", 0) or 0
        if created_utc and created_utc < cutoff_ts:
            continue
        selftext = post.get("selftext", "") or ""
        if selftext in ("[deleted]", "[removed]"):
            selftext = ""

        post_id = post.get("id", "")
        flair = post.get("link_flair_text") or ""
        created_iso = (
            datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()
            if created_utc else ""
        )

        comments: list[str] = []
        if config["top_n_comments"] > 0 and post_id and not selftext:
            # only fetch if we need comments and don't already have body from listing
            selftext, comments = await _fetch_post_comments(
                subreddit, post_id, config["top_n_comments"], crawler=crawler
            )
            await asyncio.sleep(1)
        elif config["top_n_comments"] > 0 and post_id:
            _, comments = await _fetch_post_comments(
                subreddit, post_id, config["top_n_comments"], crawler=crawler
            )
            await asyncio.sleep(1)

        section = "case_timeline" if flair in ("Approved", "Timeline") else "q_and_a"
        trust_score = 0.65 if score >= 20 else 0.5

        permalink = post.get("permalink", "")
        record = make_record(
            chunk_id=make_chunk_id("reddit", subreddit, post_id or post.get("title", "")),
            title=post.get("title", ""),
            content=_build_content(post.get("title", ""), selftext, comments),
            section=section,
            category=config["category"],
            country=config["country"],
            tags=[t for t in [flair, subreddit] if t],
            page_url=f"https://reddit.com{permalink}" if permalink else "",
            site=f"reddit_{subreddit}",
            trust_score=trust_score,
            priority=2,
            extra={
                "post_id": post_id,
                "score": score,
                "num_comments": post.get("num_comments", 0),
                "flair": flair,
                "created_utc": created_iso,
                "top_comments": comments,
            },
        )
        if record:
            chunks.append(record)
        if len(chunks) >= config["limit"]:
            break

    return chunks


class RedditCrawler(BaseCrawler):
    source_name = "reddit"

    def crawl(self) -> list[dict]:
        return asyncio.run(self._crawl_async())

    async def _crawl_async(self) -> list[dict]:
        from crawl4ai import AsyncWebCrawler, BrowserConfig

        all_chunks: list[dict] = []
        needs_browser = any(c["top_n_comments"] > 0 for c in REDDIT_SOURCES)

        if needs_browser:
            browser_cfg = BrowserConfig(headless=True, verbose=False)
            async with AsyncWebCrawler(config=browser_cfg) as crawler:
                for config in REDDIT_SOURCES:
                    logger.info("[reddit] r/%s ...", config["subreddit"])
                    chunks = await crawl_subreddit_async(config, crawler=crawler)
                    logger.info("[reddit] r/%s: %d chunks", config["subreddit"], len(chunks))
                    all_chunks.extend(chunks)
                    await asyncio.sleep(8)  # avoid RSS rate limit
        else:
            for config in REDDIT_SOURCES:
                logger.info("[reddit] r/%s ...", config["subreddit"])
                chunks = await crawl_subreddit_async(config)
                logger.info("[reddit] r/%s: %d chunks", config["subreddit"], len(chunks))
                all_chunks.extend(chunks)
                await asyncio.sleep(8)  # avoid RSS rate limit
        return all_chunks


def run(out_dir: str = "data/crawled") -> int:
    return RedditCrawler(out_dir=out_dir).run()
