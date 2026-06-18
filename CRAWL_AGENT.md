# CRAWL_AGENT.md

This file is the specification for Claude Code when building and maintaining the immigration data crawl pipeline for LNC Global Knowledge Base.

---

## Goal

Build a scheduled crawl pipeline that collects immigration data from Reddit, case tracker sites, and immigration blogs — then outputs clean JSON files compatible with the existing `KnowledgeChunk` import format used by `graph/importers/json_importer.py`.

The pipeline runs automatically via GitHub Actions on a cron schedule. Claude Code implements, maintains, and debugs all crawlers in this file.

---

## Output format (must match existing importer)

Every crawler must output a JSON array saved to `data/crawled/<source>/<YYYY-MM-DD>.json`.

> **Implementation status (2026-06-16):** `crawlers/base.py`, `crawlers/run_all.py`, and all crawlers listed under [Project structure](#project-structure-to-create) already exist and run for real (see `data/crawled/*/`). **`crawlers/base.py::make_record()` is the authoritative shape** — it nests `chunk_id`/`section`/`country`/`tags`/`trust_score`/`priority`/`language` inside `structured_data`, matching exactly what `_load_chunks_array()` in `graph/importers/json_importer.py` reads (and what CLAUDE.md's "flat-array format" describes). The example below was previously written with these fields at the top level — that was wrong; it's corrected here. Any new crawler should call `make_record()` rather than hand-building this dict.

Each item in the array follows the **flat-array format** already understood by `json_importer.py`:

```json
[
  {
    "title": "Short descriptive title of the post or thread",
    "content": "Full text content. For Reddit: title + body + top comments merged. For trackers: structured timeline text.",
    "category": "express_entry | pnp | lmia | eb2_niw | eb1 | o1 | perm | l1 | h1b | skilled_migrant | general",
    "site": "reddit_ExpressEntry",
    "page_url": "https://reddit.com/r/ExpressEntry/comments/abc123",
    "structured_data": {
      "chunk_id": "<md5 of source + post_id, via crawlers.base.make_chunk_id>",
      "section": "q_and_a | case_timeline | policy_update | draw_result | community_discussion | success_story | program_overview",
      "country": "canada | usa | new_zealand",
      "tags": ["approved", "timeline", "ielts", "noc_21232"],
      "trust_score": 0.75,
      "priority": 2,
      "language": "en",
      "post_id": "abc123",
      "author_karma": 1200,
      "score": 47,
      "num_comments": 23,
      "flair": "Approved",
      "created_utc": "2025-06-01T10:23:00Z",
      "top_comments": ["comment 1 text", "comment 2 text"]
    }
  }
]
```

**Rules:**
- `chunk_id` must be deterministic — same post always produces same ID (use `crawlers.base.make_chunk_id`, a thin `hashlib.md5` wrapper)
- `content` is the main text for embedding — make it dense and informative, not just the title; `make_record()` truncates to 4000 chars and drops anything under 100 chars
- `trust_score` scale: `0.9` = official gov source, `0.8` = verified firm/organization-published case data (e.g. law firm success stories), `0.75` = established community site, `0.6` = Reddit high-score post, `0.4` = Reddit low-score post
- `priority` scale: `1` = high (official/verified), `2` = medium (community), `3` = low (noise)
- Do NOT save duplicate `chunk_id` — `BaseCrawler.save()` already does this via a per-source `seen_ids.json`, scanned together with every existing daily file
- Empty `structured_data: {}` is allowed when no metadata is available

---

## Project structure (implemented)

```
crawlers/
  __init__.py
  base.py                              # BaseCrawler abstract class + make_chunk_id/make_record
  reddit_crawler.py                    # PRAW-based Reddit crawler
  visajourney_crawler.py               # VisaJourney case timeline crawler
  trackitt_crawler.py                  # Trackitt H1B/I-485/PERM crawler
  immitracker_crawler.py               # myimmitracker.com Canada/Australia
  rss_crawler.py                       # CIC News + Moving2Canada + Webber (one module, multiple RSS_SOURCES)
  wegreened_crawler.py                 # WeGreened latest-informations + L-1 FAQ
  wegreened_success_stories_crawler.py # WeGreened success-stories Strapi collection (7,533 records)
  wegreened_case_extractor.py          # LLM-based per-case analytics extraction — NOT a KnowledgeChunk source
  export_csv.py                        # Ad-hoc export helper
  run_all.py                           # Orchestrator: runs all crawlers, deduplicates, saves

data/
  crawled/                   # Output dir — gitignored for large files
    reddit/
    visajourney/
    trackitt/
    immitracker/
    cicnews/
    moving2canada/
    webber/
    wegreened/
    wegreened_success_stories/
    wegreened_cases/          # analytics output (JSON + CSV), not imported into Neo4j

.github/
  workflows/
    crawl_daily.yml          # Runs reddit + RSS + wegreened crawlers daily
    crawl_weekly.yml         # Runs heavy crawlers (trackitt, visajourney, immitracker) weekly
    import_to_neo4j.yml      # Triggered after crawl: imports new JSON → Neo4j + embeds

logs/
  crawl_YYYY-MM-DD.log       # Appended each run
```

---

## Crawler 1 — Reddit (PRAW)

**File:** `crawlers/reddit_crawler.py`

**Library:** `praw` — install via `pip install praw`

**Credentials needed (GitHub Secrets):**
- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USER_AGENT` (e.g. `"lnc_immigration_bot/1.0 by thtv231"`)

**Subreddits and config:**

```python
REDDIT_SOURCES = [
    # Canada
    {
        "subreddit": "ExpressEntry",
        "country": "canada",
        "category": "express_entry",
        "flairs_include": ["Approved", "Invitation", "Draw", "Timeline", "Question"],
        "min_score": 5,
        "limit": 100,
        "fetch_comments": True,
        "top_n_comments": 5,
    },
    {
        "subreddit": "ImmigrationCanada",
        "country": "canada",
        "category": "general",
        "flairs_include": None,  # all flairs
        "min_score": 10,
        "limit": 100,
        "fetch_comments": True,
        "top_n_comments": 3,
    },
    {
        "subreddit": "CanadaVisa",
        "country": "canada",
        "category": "general",
        "flairs_include": None,
        "min_score": 5,
        "limit": 80,
        "fetch_comments": True,
        "top_n_comments": 3,
    },
    {
        "subreddit": "PNP",
        "country": "canada",
        "category": "pnp",
        "flairs_include": None,
        "min_score": 3,
        "limit": 50,
        "fetch_comments": True,
        "top_n_comments": 3,
    },
    # USA
    {
        "subreddit": "USCIS",
        "country": "usa",
        "category": "general",
        "flairs_include": None,
        "min_score": 10,
        "limit": 100,
        "fetch_comments": True,
        "top_n_comments": 5,
    },
    {
        "subreddit": "immigration",
        "country": "usa",
        "category": "general",
        "flairs_include": None,
        "min_score": 15,
        "limit": 80,
        "fetch_comments": False,
    },
    {
        "subreddit": "EB2NIW",
        "country": "usa",
        "category": "eb2_niw",
        "flairs_include": ["Approved", "RFE", "Denied", "Timeline"],
        "min_score": 3,
        "limit": 100,
        "fetch_comments": True,
        "top_n_comments": 5,
    },
    # New Zealand
    {
        "subreddit": "NZImmigration",
        "country": "new_zealand",
        "category": "skilled_migrant",
        "flairs_include": None,
        "min_score": 3,
        "limit": 50,
        "fetch_comments": True,
        "top_n_comments": 3,
    },
]
```

**Implementation logic:**

```python
import praw, hashlib, json
from datetime import datetime, timezone

def build_chunk_id(subreddit: str, post_id: str) -> str:
    raw = f"reddit_{subreddit}_{post_id}"
    return hashlib.md5(raw.encode()).hexdigest()

def build_content(post, top_comments: list[str]) -> str:
    parts = [post.title]
    if post.selftext and len(post.selftext) > 20:
        parts.append(post.selftext[:3000])
    if top_comments:
        parts.append("Community responses:")
        parts.extend(f"- {c[:500]}" for c in top_comments)
    return "\n\n".join(parts)

def crawl_subreddit(reddit, config: dict) -> list[dict]:
    sub = reddit.subreddit(config["subreddit"])
    chunks = []
    for post in sub.new(limit=config["limit"]):
        if post.score < config["min_score"]:
            continue
        if config["flairs_include"] and post.link_flair_text not in config["flairs_include"]:
            continue

        comments = []
        if config.get("fetch_comments"):
            post.comments.replace_more(limit=0)
            top = sorted(post.comments.list(), key=lambda c: c.score, reverse=True)
            comments = [c.body for c in top[:config["top_n_comments"]] if hasattr(c, "body")]

        chunk = {
            "chunk_id": build_chunk_id(config["subreddit"], post.id),
            "title": post.title[:200],
            "section": "case_timeline" if post.link_flair_text in ["Approved", "Timeline"] else "q_and_a",
            "content": build_content(post, comments),
            "category": config["category"],
            "country": config["country"],
            "tags": [t for t in [post.link_flair_text, config["subreddit"]] if t],
            "source_url": f"https://reddit.com{post.permalink}",
            "site": f"reddit_{config['subreddit']}",
            "trust_score": 0.65 if post.score >= 20 else 0.5,
            "priority": 2,
            "language": "en",
            "structured_data": {
                "post_id": post.id,
                "score": post.score,
                "num_comments": post.num_comments,
                "flair": post.link_flair_text,
                "created_utc": datetime.fromtimestamp(post.created_utc, tz=timezone.utc).isoformat(),
                "top_comments": comments,
            },
        }
        chunks.append(chunk)
    return chunks
```

**Rate limiting:** PRAW handles Reddit's 60 requests/minute automatically. Add `time.sleep(1)` between subreddits.

**Deduplication:** Before saving, load the existing daily file if it exists and skip any `chunk_id` already present. Also maintain a `data/crawled/reddit/seen_ids.json` set across runs.

---

## Crawler 2 — VisaJourney (case timelines)

**File:** `crawlers/visajourney_crawler.py`

**Library:** `httpx`, `beautifulsoup4`

**Target pages:**
- `https://www.visajourney.com/timeline/` — employment-based timelines
- `https://www.visajourney.com/forums/` — forum posts

**Strategy:** Parse HTML tables from timeline pages. Each row = one applicant's timeline (filed date, approval date, service center, case type). Convert to structured content text:

```python
def timeline_row_to_content(row: dict) -> str:
    return (
        f"Case type: {row['case_type']}\n"
        f"Filed: {row['filed_date']} | Service center: {row['service_center']}\n"
        f"Approved: {row['approved_date']} | Processing time: {row['days']} days\n"
        f"Country of birth: {row['country_of_birth']}"
    )
```

**chunk_id:** MD5 of `visajourney_{case_type}_{filed_date}_{service_center}_{row_index}`

**Output section:** `"case_timeline"`

**Rate limiting:** 1 request every 3 seconds. Use `httpx` with `follow_redirects=True`. Set `User-Agent: "Mozilla/5.0"` header.

**Note:** VisaJourney may paginate — handle `?page=N` params and stop at page 10 or when data is older than 180 days.

---

## Crawler 3 — Trackitt (H1B, I-485, PERM, EAD)

**File:** `crawlers/trackitt_crawler.py`

**Library:** `httpx`, `beautifulsoup4`

**Target URLs:**
```python
TRACKITT_URLS = [
    ("https://www.trackitt.com/usa-immigration-trackers/i485", "i485", "usa"),
    ("https://www.trackitt.com/usa-immigration-trackers/i140", "i140", "usa"),
    ("https://www.trackitt.com/usa-immigration-trackers/h1b", "h1b", "usa"),
    ("https://www.trackitt.com/usa-immigration-trackers/perm", "perm", "usa"),
    ("https://www.trackitt.com/usa-immigration-trackers/ead", "ead", "usa"),
]
```

**Strategy:** Similar to VisaJourney — parse tracker tables, convert each case row to a text chunk. Focus on columns: receipt date, approval date, service center, nationality, current status.

**Output category mapping:**
- `i485`, `i140` → `"eb2_niw"` or `"eb1"` depending on thread context
- `h1b` → `"h1b"`
- `perm` → `"general"`

---

## Crawler 4 — myimmitracker.com (Canada & Australia)

**File:** `crawlers/immitracker_crawler.py`

**Library:** `httpx`, `beautifulsoup4`

**Target:** Canada application trackers — Express Entry, PNP, spousal sponsorship.

**URL pattern:** `https://myimmitracker.com/ca/trackers/<program-slug>`

**Programs to track:**
```python
IMMITRACKER_PROGRAMS = [
    ("express-entry", "express_entry", "canada"),
    ("pnp-streams", "pnp", "canada"),
    ("spousal-sponsorship", "general", "canada"),
    ("lmia", "lmia", "canada"),
]
```

**Strategy:** Parse the tracker table (application date, AOR, PPR, COPR) and comments. Convert timeline to natural language text for embedding.

---

## Crawler 5 — RSS feeds (CIC News, Moving2Canada, Webber Substack)

**File:** `crawlers/rss_crawler.py`

**Library:** `feedparser` — install via `pip install feedparser`

**RSS sources config:**
```python
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
        "name": "webber_immigration",
        "url": "https://webberimmigration.substack.com/feed",
        "country": "usa",
        "category": "eb2_niw",
        "section": "case_timeline",
        "trust_score": 0.85,
        "priority": 1,
        "language": "en",
    },
    {
        "name": "ilw_news",
        "url": "https://www.ilw.com/immigrationdaily/news/rss.shtm",
        "country": "usa",
        "category": "general",
        "section": "policy_update",
        "trust_score": 0.80,
        "priority": 1,
        "language": "en",
    },
]
```

**Implementation:**

```python
import feedparser, hashlib, httpx
from bs4 import BeautifulSoup

def chunk_id_from_url(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def extract_full_text(entry) -> str:
    # Try summary, then content, then fetch full page
    if hasattr(entry, "content"):
        html = entry.content[0].value
        return BeautifulSoup(html, "html.parser").get_text(separator="\n")[:5000]
    if hasattr(entry, "summary"):
        return BeautifulSoup(entry.summary, "html.parser").get_text()[:3000]
    return entry.get("title", "")

def crawl_rss(source: dict) -> list[dict]:
    feed = feedparser.parse(source["url"])
    chunks = []
    for entry in feed.entries:
        chunk = {
            "chunk_id": chunk_id_from_url(entry.get("link", entry.get("id", ""))),
            "title": entry.get("title", "")[:200],
            "section": source["section"],
            "content": extract_full_text(entry),
            "category": source["category"],
            "country": source["country"],
            "tags": [t.term for t in entry.get("tags", [])],
            "source_url": entry.get("link", ""),
            "site": source["name"],
            "trust_score": source["trust_score"],
            "priority": source["priority"],
            "language": source["language"],
            "structured_data": {
                "published": entry.get("published", ""),
                "author": entry.get("author", ""),
            },
        }
        chunks.append(chunk)
    return chunks
```

---

## Crawler 6 — WeGreened (NAILG success stories + approvals)

**Status: implemented.** Real architecture differs from the WordPress-RSS assumption this section originally documented — confirmed by direct HTTP calls on 2026-06-16, see below. Three files exist; none scrape HTML:

| File | Strapi collection / endpoint | Section | Cadence |
|---|---|---|---|
| `crawlers/wegreened_crawler.py` | `latest-informations` (monthly/periodic approval-count announcements) + the L-1 visa FAQ page's JSON-LD `structuredData` | `approvals`, `faq` | daily |
| `crawlers/wegreened_success_stories_crawler.py` | `success-stories` — **7,533 records**, covers both individual NIW/EB-1/O-1 narrative case write-ups *and* the recurring "Daily Approval Summary" digest posts | `success_story`, `draw_result` | daily (newest-first, stops early once a page has no new records) |
| `crawlers/wegreened_case_extractor.py` | reuses `wegreened_crawler.py`'s `latest-informations` fetch, then runs each digest article through a Groq LLM to pull structured per-case analytics rows (citations, processing days, RFE, etc.) | n/a — **not** a `KnowledgeChunk` source, writes `data/crawled/wegreened_cases/*.json` + a consolidated CSV, intentionally not wired into `json_importer.py` | daily |

**Real source, not WordPress:** `wegreened.com` is a Nuxt.js SSR frontend backed by a public, unauthenticated Strapi CMS REST API at `https://cms.wegreened.com/api`. A legacy-looking WordPress feed *also* exists at `https://www.wegreened.com/blog/feed` (verified live, title "Chen Immigration Blog") and happens to mirror the same underlying content, but the Strapi API is strictly better for crawling: full pagination/backfill, `sort=publishedDate:desc` for cheap incremental runs, and pre-structured fields (`blog_categories`, `blog_tags`, `blog_country`, `client_field`, `client_position`, `blog_citation_range`, `canonical` URL) instead of prose that would need LLM extraction. Don't add an RSS-based crawler for this site — it would just duplicate the API path with less structure.

**`robots.txt` compliance (checked 2026-06-16):**
- `www.wegreened.com/robots.txt` disallows `/api/*`, `/*?pdf=*` (the `Approval_Viewer` scanned-PDF gallery at `/eb1_niw_approvals`), `/*?date=`, `/*?tag=`, `/*?month=`, `/*?locale=`, `/trademark*`, `/Our-Team*` (attorney profiles — explicitly out of scope, do not build a "profile crawler" for this site).
- `cms.wegreened.com/robots.txt` has no active rules (the `Disallow: /` block is commented out) — the API is openly crawlable.
- **Never** OCR or scrape the `Approval_Viewer` PDF thumbnails even though they're visually public — scanned USCIS notices, excluded both by `robots.txt` and by the PII rule in [Data quality rules](#data-quality-rules-claude-code-phải-enforce).

**Classifying `success-stories` records** (see `wegreened_success_stories_crawler.py::_classify`): a record's `blog_categories[].slug` is checked against a small map (`niw`→`eb2_niw`, `eb1-green-card`→`eb1`, `success-stories-o1-a`→`o1`); `daily-approval-summary` in that list flags it as a digest (`section: draw_result`) instead of a narrative case (`section: success_story`). Everything else in `blog_categories` (~380 research-field taxonomy entries, e.g. "Analytical Chemistry") is not a visa category — it goes into `tags`, not `category`. No L-1, PERM, or H-1B success stories exist in this collection (WeGreened's core practice is NIW/EB-1/O-1); L-1 is covered separately via the static FAQ page in `wegreened_crawler.py`.

**Known quirk:** `canonical` (the ready-made relative URL) is `null` on most digest records even though the live site serves them at `/blog/daily-approval-summary/<slug>/` — the crawler reconstructs that path when `canonical` is missing instead of falling back to a bare `/blog/<slug>/`.

---

## Orchestrator

**File:** `crawlers/run_all.py` — **implemented**, see the real file for the current dispatch logic (one `if "<source>" in sources:` branch per crawler, each calling that module's `run(out_dir=...)`). Current source lists:

```python
DAILY_SOURCES  = ["reddit", "cicnews", "moving2canada", "webber",
                  "wegreened", "wegreened_cases", "wegreened_success_stories"]
WEEKLY_SOURCES = ["visajourney", "trackitt", "immitracker"]
RSS_SOURCES    = ["cicnews", "moving2canada", "webber"]   # all handled by rss_crawler.py
```

```bash
python -m crawlers.run_all --mode daily
python -m crawlers.run_all --mode weekly      # daily + weekly sources
python -m crawlers.run_all --sources reddit cicnews wegreened_success_stories
```

Adding a new source = one new module exposing `run(out_dir: str = "data/crawled") -> int` (a thin wrapper around a `BaseCrawler` subclass, per `crawlers/base.py`), plus one line in the relevant `*_SOURCES` list and one `if`-branch in `main()`.

---

## GitHub Actions workflows

### `.github/workflows/crawl_daily.yml`

```yaml
name: Crawl daily (Reddit + RSS + WeGreened)

on:
  schedule:
    - cron: "0 2 * * *"   # 2:00 AM UTC = 9:00 AM Vietnam time, mỗi ngày
  workflow_dispatch:        # cho phép chạy thủ công

jobs:
  crawl:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements-crawl.txt

      - name: Run daily crawlers
        env:
          REDDIT_CLIENT_ID: ${{ secrets.REDDIT_CLIENT_ID }}
          REDDIT_CLIENT_SECRET: ${{ secrets.REDDIT_CLIENT_SECRET }}
          REDDIT_USER_AGENT: ${{ secrets.REDDIT_USER_AGENT }}
        run: python -m crawlers.run_all --mode daily

      - name: Commit crawled data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/crawled/
          git diff --staged --quiet || git commit -m "chore: daily crawl $(date -u +%Y-%m-%d)"
          git push
```

### `.github/workflows/crawl_weekly.yml`

```yaml
name: Crawl weekly (VisaJourney + Trackitt + Immitracker)

on:
  schedule:
    - cron: "0 3 * * 0"   # 3:00 AM UTC Chủ nhật = 10:00 AM Vietnam
  workflow_dispatch:

jobs:
  crawl-heavy:
    runs-on: ubuntu-latest
    timeout-minutes: 60

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements-crawl.txt

      - name: Run weekly crawlers
        run: python -m crawlers.run_all --mode weekly

      - name: Commit crawled data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/crawled/
          git diff --staged --quiet || git commit -m "chore: weekly crawl $(date -u +%Y-%m-%d)"
          git push
```

### `.github/workflows/import_to_neo4j.yml`

```yaml
name: Import crawled data → Neo4j + embed

on:
  workflow_run:
    workflows: ["Crawl daily (Reddit + RSS + WeGreened)"]
    types: [completed]
  workflow_dispatch:
    inputs:
      data_dir:
        description: "Subdir to import (e.g. reddit, cicnews, or 'all')"
        default: "all"

jobs:
  import:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' || github.event_name == 'workflow_dispatch' }}
    timeout-minutes: 45

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Import new JSON files
        env:
          NEO4J_URI: ${{ secrets.NEO4J_URI }}
          NEO4J_USER: ${{ secrets.NEO4J_USER }}
          NEO4J_PASSWORD: ${{ secrets.NEO4J_PASSWORD }}
        run: |
          DATA_DIR="${{ github.event.inputs.data_dir || 'all' }}"
          if [ "$DATA_DIR" = "all" ]; then
            for subdir in data/crawled/*/; do
              python -m graph.importers.json_importer --data-dir "$subdir" --recursive
            done
          else
            python -m graph.importers.json_importer --data-dir "data/crawled/$DATA_DIR" --recursive
          fi

      - name: Generate embeddings for new chunks
        env:
          NEO4J_URI: ${{ secrets.NEO4J_URI }}
          NEO4J_USER: ${{ secrets.NEO4J_USER }}
          NEO4J_PASSWORD: ${{ secrets.NEO4J_PASSWORD }}
        run: |
          python -m embeddings.embed_nodes --label KnowledgeChunk --batch-size 32
```

---

## requirements-crawl.txt

```
praw==7.7.1
feedparser==6.0.11
httpx==0.27.0
beautifulsoup4==4.12.3
lxml==5.2.2
```

---

## GitHub Secrets cần thiết

Vào `Settings → Secrets and variables → Actions` trong repo và thêm:

| Secret | Giá trị | Dùng cho |
|--------|---------|---------|
| `REDDIT_CLIENT_ID` | Lấy từ reddit.com/prefs/apps | Reddit crawler |
| `REDDIT_CLIENT_SECRET` | Lấy từ reddit.com/prefs/apps | Reddit crawler |
| `REDDIT_USER_AGENT` | `"lnc_immigration_bot/1.0 by thtv231"` | Reddit crawler |
| `NEO4J_URI` | `neo4j+s://xxxxxxxx.databases.neo4j.io` | Import workflow |
| `NEO4J_USER` | `neo4j` | Import workflow |
| `NEO4J_PASSWORD` | password của AuraDB | Import workflow |

> **WeGreened crawler không cần secret nào** — feed (`/blog/feed`) và các program page đều public, không cần auth.

**Cách tạo Reddit app:**
1. Vào https://www.reddit.com/prefs/apps
2. Click "create another app" → chọn **script**
3. Name: `lnc_immigration_bot`, redirect uri: `http://localhost:8080`
4. Copy `client_id` (dưới tên app) và `client_secret`

---

## .gitignore additions

Add to `.gitignore`:

```
# Crawled data — commit only metadata, not bulk JSON
data/crawled/**/*.json
!data/crawled/.gitkeep

# Keep seen_ids tracking files
!data/crawled/*/seen_ids.json

# Logs
logs/
```

> **Lưu ý:** Nếu muốn commit toàn bộ data vào repo (cho đơn giản), xóa dòng `data/crawled/**/*.json` khỏi gitignore. AuraDB Free có limit 200k nodes — nên chỉ import không commit raw JSON vào repo.

---

## Data quality rules (Claude Code phải enforce)

1. **Minimum content length:** Bỏ qua bất kỳ chunk nào có `content` dưới 100 ký tự.
2. **No deleted posts:** Reddit posts có `[deleted]` hoặc `[removed]` trong selftext → skip.
3. **No spam/bot patterns:** Skip posts từ account karma < 10 hoặc selftext chứa links liên tục.
4. **Language detection:** Nếu content chủ yếu không phải EN, set `language: "vi"` hoặc `"mixed"`. Dùng `langdetect` nếu cần.
5. **Content cap:** Truncate `content` tại 4000 ký tự để không vượt quá token limit khi embed.
6. **Date filter:** Với Reddit và trackers, chỉ lấy posts trong 90 ngày qua (daily run) hoặc 1 năm (weekly historical run).
7. **Respect `robots.txt`:** Trước khi thêm crawler cho bất kỳ site mới nào, đọc `robots.txt` của site đó và liệt kê path bị `Disallow`. Không bao giờ crawl path bị disallow, kể cả khi nội dung "nhìn có vẻ public". Với WeGreened: không crawl `/Our-Team*` (hồ sơ luật sư) và `/*?pdf=*` (gallery `Approval_Viewer`).
8. **No scanned-document PII:** Không OCR hoặc lưu trữ ảnh/PDF scan của approval notice gốc (vd. `Approval_Viewer` của WeGreened) — đây là văn bản chính phủ có thể chứa tên/số hồ sơ thật chưa được redact đầy đủ. Chỉ lấy nội dung text đã được chính nguồn viết lại/redact công khai (blog success story, case study).

---

## Monitoring & alerts

Thêm step sau mỗi workflow để report tóm tắt:

```yaml
- name: Summary report
  if: always()
  run: |
    echo "## Crawl Summary" >> $GITHUB_STEP_SUMMARY
    echo "| Source | New chunks |" >> $GITHUB_STEP_SUMMARY
    echo "|--------|-----------|" >> $GITHUB_STEP_SUMMARY
    for f in data/crawled/*/*.json; do
      source=$(basename $(dirname $f))
      count=$(python -c "import json; data=json.load(open('$f')); print(len(data))" 2>/dev/null || echo 0)
      echo "| $source | $count |" >> $GITHUB_STEP_SUMMARY
    done
```

---

## Implementation order for Claude Code

**Status (2026-06-16): steps 1–10 are done.** `base.py`, `rss_crawler.py`, `reddit_crawler.py`, `run_all.py`, both workflow files, and the heavy/weekly crawlers all exist and have produced real output under `data/crawled/`. WeGreened is covered by `wegreened_crawler.py` + `wegreened_success_stories_crawler.py` (§ above) instead of the originally-planned feed/program-page split. Step 11 (monitoring) has not been added yet.

For any **new** source going forward, follow the same build → test → verify pattern that was used here:

1. Probe the real site first — fetch `robots.txt`, check whether it's a static page, an RSS feed, or (as WeGreened turned out to be) a CMS REST API; don't assume from the rendered page alone.
2. Write the module against `crawlers/base.py` — subclass `BaseCrawler`, build records with `make_record()`/`make_chunk_id()` so the output shape is correct by construction (see the corrected [Output format](#output-format-must-match-existing-importer)).
3. Smoke-test against the live source directly (a small Python one-liner hitting just the crawler's internal fetch function) before running a full `crawl()` — these endpoints are sometimes flaky (see the retry wrapper in `wegreened_crawler.py`) and a full run can be slow on a large backlog.
4. Verify output is compatible with `json_importer.py` by importing a sample file.
5. Add one entry to `DAILY_SOURCES` or `WEEKLY_SOURCES` in `run_all.py` and one dispatch branch in `main()` — nothing else needs to change in the orchestrator.
6. Add monitoring step to all workflows once a few more sources land — not worth doing for just one.

**Do NOT implement multiple new crawlers in one pass.** Build → test → verify format → next.
