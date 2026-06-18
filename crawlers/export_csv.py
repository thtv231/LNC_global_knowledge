"""Export all crawled data from data/crawled/ and data/crawled_test/ into a single CSV."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from datetime import datetime


COLUMNS = [
    "source",
    "crawl_date",
    "country",
    "category",
    "section",
    "title",
    "content_preview",
    "url",
    "trust_score",
    "priority",
    "tags",
    "comments_count",
    "score",
    "chunk_id",
]


def _load_dir(base: Path) -> list[dict]:
    rows = []
    for json_file in sorted(base.rglob("*.json")):
        if json_file.name in ("seen_ids.json",):
            continue
        try:
            records = json.loads(json_file.read_text(encoding="utf-8"))
            if not isinstance(records, list):
                continue
        except Exception:
            continue

        # infer crawl_date from filename (YYYY-MM-DD.json)
        crawl_date = json_file.stem if len(json_file.stem) == 10 else ""
        source_dir = json_file.parent.name

        for r in records:
            sd = r.get("structured_data", {})
            content = r.get("content", "")
            # first 200 chars, single line
            preview = content[:200].replace("\n", " ").replace("\r", "")

            top_comments = sd.get("top_comments", [])

            rows.append({
                "source":          r.get("site") or source_dir,
                "crawl_date":      crawl_date,
                "country":         sd.get("country", ""),
                "category":        r.get("category", ""),
                "section":         sd.get("section", ""),
                "title":           r.get("title", ""),
                "content_preview": preview,
                "url":             r.get("page_url", ""),
                "trust_score":     sd.get("trust_score", ""),
                "priority":        sd.get("priority", ""),
                "tags":            "|".join(sd.get("tags", [])),
                "comments_count":  len(top_comments),
                "score":           sd.get("score", ""),
                "chunk_id":        sd.get("chunk_id", ""),
            })
    return rows


def main():
    parser = argparse.ArgumentParser(description="Export crawled data to CSV")
    parser.add_argument("--dirs", nargs="*", default=["data/crawled", "data/crawled_test"],
                        help="Directories to read JSON from")
    parser.add_argument("--out", default="data/crawled_all.csv", help="Output CSV path")
    args = parser.parse_args()

    all_rows: list[dict] = []
    for d in args.dirs:
        p = Path(d)
        if p.exists():
            rows = _load_dir(p)
            print(f"{d}: {len(rows)} records")
            all_rows.extend(rows)

    # deduplicate by chunk_id
    seen: set[str] = set()
    unique_rows = []
    for r in all_rows:
        cid = r["chunk_id"]
        if cid and cid in seen:
            continue
        seen.add(cid)
        unique_rows.append(r)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(unique_rows)

    print(f"\nExported {len(unique_rows)} unique chunks -> {out}")

    # print summary by source
    from collections import Counter
    by_source = Counter(r["source"] for r in unique_rows)
    print("\nBy source:")
    for src, count in sorted(by_source.items()):
        print(f"  {src:<30} {count}")


if __name__ == "__main__":
    main()
