from __future__ import annotations
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


def make_chunk_id(*parts: str) -> str:
    raw = "_".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()


def make_record(
    *,
    chunk_id: str,
    title: str,
    content: str,
    section: str,
    category: str,
    country: str,
    tags: list[str],
    page_url: str,
    site: str,
    trust_score: float,
    priority: int,
    language: str = "en",
    extra: dict | None = None,
) -> dict:
    """Build a record in the flat-array format expected by json_importer.py."""
    if len(content) < 100:
        return {}
    content = content[:4000]
    structured = {
        "chunk_id": chunk_id,
        "section": section,
        "country": country,
        "tags": [t for t in tags if t],
        "trust_score": trust_score,
        "priority": priority,
        "language": language,
    }
    if extra:
        structured.update(extra)
    return {
        "content": content,
        "title": title[:200],
        "category": category,
        "site": site,
        "page_url": page_url,
        "structured_data": structured,
    }


class BaseCrawler(ABC):
    source_name: str = ""

    def __init__(self, out_dir: str = "data/crawled"):
        self.out_dir = Path(out_dir) / self.source_name
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def _load_seen_ids(self) -> set[str]:
        seen_file = self.out_dir / "seen_ids.json"
        if seen_file.exists():
            try:
                return set(json.loads(seen_file.read_text(encoding="utf-8")))
            except Exception:
                pass
        # also scan existing daily files
        seen: set[str] = set()
        for f in self.out_dir.glob("*.json"):
            if f.name == "seen_ids.json":
                continue
            try:
                records = json.loads(f.read_text(encoding="utf-8"))
                for r in records:
                    cid = r.get("structured_data", {}).get("chunk_id")
                    if cid:
                        seen.add(cid)
            except Exception:
                pass
        return seen

    def _save_seen_ids(self, seen: set[str]) -> None:
        seen_file = self.out_dir / "seen_ids.json"
        seen_file.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")

    def save(self, chunks: list[dict]) -> int:
        seen = self._load_seen_ids()
        new_chunks = []
        for c in chunks:
            if not c:
                continue
            cid = c.get("structured_data", {}).get("chunk_id", "")
            if cid and cid not in seen:
                new_chunks.append(c)
                seen.add(cid)

        if new_chunks:
            out_file = self.out_dir / f"{date.today().isoformat()}.json"
            # append to today's file if it exists
            existing = []
            if out_file.exists():
                try:
                    existing = json.loads(out_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            out_file.write_text(
                json.dumps(existing + new_chunks, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._save_seen_ids(seen)
            logger.info("[%s] Saved %d new chunks -> %s", self.source_name, len(new_chunks), out_file)
        else:
            logger.info("[%s] No new chunks.", self.source_name)

        return len(new_chunks)

    @abstractmethod
    def crawl(self) -> list[dict]:
        ...

    def run(self) -> int:
        logger.info("[%s] Starting crawl...", self.source_name)
        chunks = self.crawl()
        return self.save(chunks)
