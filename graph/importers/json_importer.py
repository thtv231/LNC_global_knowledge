"""Import pre-chunked JSON files from data/ and data2/ directories into Neo4j KnowledgeChunk nodes.

Supports two layouts:
  - flat:      <dir>/*.json  where each file is a JSON array of chunk objects (original format)
  - recursive: <dir>/**/*.json  where each file is a single JSON object (data2 format)
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase
from tqdm import tqdm

load_dotenv()

BATCH_SIZE = 500

_COUNTRY_MAP = {
    "data_canada": "canada",
    "canada": "canada",
    "data_usa": "usa",
    "data_my": "usa",
    "mỹ": "usa",
    "my": "usa",
    "data_newzealand": "newzealand",
    "newzealand": "newzealand",
}


def _country_from_path(path: Path) -> str:
    for part in path.parts:
        key = part.lower().replace(" ", "_")
        if key in _COUNTRY_MAP:
            return _COUNTRY_MAP[key]
    return "unknown"


def _make_chunk_id(page_url: str, file_stem: str) -> str:
    if page_url:
        return hashlib.md5(page_url.encode()).hexdigest()[:16]
    return file_stem


# ── Original format: each file is a JSON array ──────────────────────────────

def _load_chunks_array(file_path: Path, default_country: str) -> list[dict]:
    records = json.loads(file_path.read_text(encoding="utf-8-sig"))
    if isinstance(records, dict):
        records = [records]
    chunks = []
    for item in records:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        sd = item.get("structured_data") or {}
        country = sd.get("country") or default_country
        chunk_id = sd.get("chunk_id") or f"{file_path.stem}__{len(chunks)}"
        chunks.append({
            "chunk_id": chunk_id,
            "content": content,
            "title": (item.get("title") or "").strip(),
            "section": (sd.get("section") or "").strip(),
            "category": (item.get("category") or file_path.stem).strip(),
            "country": country,
            "tags": sd.get("tags") or [],
            "source_url": item.get("page_url") or "",
            "site": item.get("site") or "",
            "trust_score": float(sd.get("trust_score") or 0.5),
            "priority": sd.get("priority") or "P3",
            "language": sd.get("language") or "en",
        })
    return chunks


# ── data2 format: each file is a single JSON object ─────────────────────────

def _load_chunk_single(file_path: Path, default_country: str) -> dict | None:
    try:
        item = json.loads(file_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if isinstance(item, list):
        # fall back to array loader
        return None
    content = (item.get("content") or "").strip()
    if not content or item.get("status") == "error":
        return None
    country = _country_from_path(file_path) or default_country
    return {
        "chunk_id": _make_chunk_id(item.get("page_url", ""), file_path.stem),
        "content": content,
        "title": (item.get("title") or "").strip(),
        "section": "",
        "category": (item.get("category") or "general").strip(),
        "country": country,
        "tags": [],
        "source_url": item.get("page_url") or "",
        "site": item.get("site") or "",
        "trust_score": 0.7,
        "priority": "P2",
        "language": "en",
    }


# ── Neo4j upsert ─────────────────────────────────────────────────────────────

_MERGE_CYPHER = """
UNWIND $batch AS c
MERGE (n:KnowledgeChunk {chunk_id: c.chunk_id})
SET n.content    = c.content,
    n.title      = c.title,
    n.section    = c.section,
    n.category   = c.category,
    n.country    = c.country,
    n.tags       = c.tags,
    n.source_url = c.source_url,
    n.site       = c.site,
    n.trust_score = c.trust_score,
    n.priority   = c.priority,
    n.language   = c.language
"""


def _flush(session, batch: list[dict]) -> None:
    if batch:
        session.run(_MERGE_CYPHER, batch=batch)


def _import_flat(session, data_dir: Path, default_country: str, files: list[Path] | None) -> int:
    json_files = files or sorted(data_dir.glob("*.json"))
    total = 0
    for f in json_files:
        chunks = _load_chunks_array(f, default_country)
        for i in tqdm(range(0, len(chunks), BATCH_SIZE), desc=f.name, leave=False):
            _flush(session, chunks[i: i + BATCH_SIZE])
        print(f"{f.name}: {len(chunks)} chunks")
        total += len(chunks)
    return total


def _import_recursive(session, data_dir: Path, default_country: str) -> int:
    all_files = sorted(data_dir.rglob("*.json"))
    print(f"Found {len(all_files)} JSON files under {data_dir}")
    batch: list[dict] = []
    total = 0
    for f in tqdm(all_files, unit="file"):
        chunk = _load_chunk_single(f, default_country)
        if chunk is None:
            # try array format fallback
            chunks = _load_chunks_array(f, default_country)
            batch.extend(chunks)
            total += len(chunks)
        else:
            batch.append(chunk)
            total += 1
        if len(batch) >= BATCH_SIZE:
            _flush(session, batch)
            batch.clear()
    _flush(session, batch)
    return total


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Import JSON knowledge chunks to Neo4j")
    parser.add_argument("--data-dir", required=True, help="Root directory containing JSON files")
    parser.add_argument("--country", choices=["canada", "usa", "newzealand"],
                        help="Override country tag (default: infer from path)")
    parser.add_argument("--recursive", action="store_true",
                        help="Recurse into subdirectories (data2 format)")
    parser.add_argument("--files", nargs="*", help="Specific filenames — flat mode only")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    default_country = args.country or _country_from_path(data_dir)

    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    with driver.session() as session:
        if args.recursive:
            total = _import_recursive(session, data_dir, default_country)
        else:
            files = [data_dir / f for f in args.files] if args.files else None
            total = _import_flat(session, data_dir, default_country, files)
    driver.close()
    print(f"\nTotal imported: {total} chunks")


if __name__ == "__main__":
    main()
