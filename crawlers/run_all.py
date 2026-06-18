"""
Orchestrator for all crawlers.

Usage:
  python -m crawlers.run_all --mode daily
  python -m crawlers.run_all --mode weekly
  python -m crawlers.run_all --sources reddit cicnews moving2canada
"""
from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path

DAILY_SOURCES = ["reddit", "cicnews", "moving2canada", "webber", "wegreened", "wegreened_cases", "wegreened_success_stories"]
WEEKLY_SOURCES = ["visajourney", "trackitt", "immitracker"]
RSS_SOURCES = ["cicnews", "moving2canada", "webber"]


def setup_logging(out_dir: str) -> None:
    from datetime import date

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"crawl_{date.today().isoformat()}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="LNC crawl orchestrator")
    parser.add_argument("--mode", choices=["daily", "weekly", "all"], default="daily")
    parser.add_argument("--sources", nargs="*", help="Specific source names to run")
    parser.add_argument("--out-dir", default="data/crawled", help="Output base directory")
    args = parser.parse_args()

    setup_logging(args.out_dir)
    logger = logging.getLogger(__name__)

    if args.sources:
        sources = args.sources
    elif args.mode == "daily":
        sources = DAILY_SOURCES
    elif args.mode == "weekly":
        sources = DAILY_SOURCES + WEEKLY_SOURCES
    else:
        sources = DAILY_SOURCES + WEEKLY_SOURCES

    logger.info("Mode: %s | Sources: %s", args.mode, sources)
    results: dict[str, int] = {}

    # RSS sources (cicnews, moving2canada, webber, ilw)
    rss_targets = [s for s in sources if s in RSS_SOURCES]
    if rss_targets:
        from crawlers.rss_crawler import run as run_rss
        rss_results = run_rss(sources=rss_targets, out_dir=args.out_dir)
        results.update(rss_results)

    if "reddit" in sources:
        from crawlers.reddit_crawler import run as run_reddit
        results["reddit"] = run_reddit(out_dir=args.out_dir)

    if "visajourney" in sources:
        from crawlers.visajourney_crawler import run as run_vj
        results["visajourney"] = run_vj(out_dir=args.out_dir)

    if "trackitt" in sources:
        from crawlers.trackitt_crawler import run as run_trackitt
        results["trackitt"] = run_trackitt(out_dir=args.out_dir)

    if "immitracker" in sources:
        from crawlers.immitracker_crawler import run as run_immi
        results["immitracker"] = run_immi(out_dir=args.out_dir)

    if "wegreened" in sources:
        from crawlers.wegreened_crawler import run as run_wegreened
        results["wegreened"] = run_wegreened(out_dir=args.out_dir)

    if "wegreened_cases" in sources:
        from crawlers.wegreened_case_extractor import run as run_wegreened_cases
        results["wegreened_cases"] = run_wegreened_cases(out_dir=args.out_dir)

    if "wegreened_success_stories" in sources:
        from crawlers.wegreened_success_stories_crawler import run as run_wegreened_stories
        results["wegreened_success_stories"] = run_wegreened_stories(out_dir=args.out_dir)

    logger.info("=== Crawl complete ===")
    total = 0
    for source, count in results.items():
        logger.info("  %-20s %d new chunks", source, count)
        total += count
    logger.info("  %-20s %d", "TOTAL", total)


if __name__ == "__main__":
    main()
