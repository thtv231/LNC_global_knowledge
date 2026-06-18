"""HuggingFace Inference API embedder — no local GPU required."""
from __future__ import annotations
import math
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

_MAX_RETRIES = 6
_RETRY_BASE = 8  # base wait seconds, doubles each attempt
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm else vec


def _extract_embedding(output: list) -> list[float]:
    """Handle both sentence-level [dim] and token-level [n_tokens, dim] outputs."""
    if isinstance(output[0], float):
        return output          # already a sentence embedding
    return output[0]           # token embeddings → take CLS token (index 0)


class HFEmbedder:
    """Calls HuggingFace feature-extraction Inference API for batch embeddings."""

    def __init__(self) -> None:
        self.model = os.environ.get("HF_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
        self.url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.model}"
        self.headers = {"Authorization": f"Bearer {os.environ['HUGGINGFACE_API_KEY']}"}
        self._req_interval = 1.1  # seconds between requests to avoid 429
        self._last_req: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of document texts. Returns list of normalised vectors."""
        self._throttle()
        data = self._call(texts)
        if len(texts) == 1:
            return [_normalize(_extract_embedding(data))]
        return [_normalize(_extract_embedding(item)) for item in data]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single search query (adds BGE instruction prefix)."""
        return self.embed([_BGE_QUERY_PREFIX + text])[0]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call(self, texts: list[str]) -> list:
        for attempt in range(_MAX_RETRIES):
            resp = requests.post(
                self.url,
                headers=self.headers,
                json={"inputs": texts, "options": {"wait_for_model": True}},
                timeout=180,
            )
            if resp.status_code == 200:
                return resp.json()
            wait = _RETRY_BASE * (2 ** attempt)
            if resp.status_code in (429, 503):
                print(f"[HF] HTTP {resp.status_code} — retrying in {wait}s (attempt {attempt + 1}/{_MAX_RETRIES})")
                time.sleep(wait)
            else:
                resp.raise_for_status()
        raise RuntimeError(f"HF API failed after {_MAX_RETRIES} attempts")

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_req
        if elapsed < self._req_interval:
            time.sleep(self._req_interval - elapsed)
        self._last_req = time.monotonic()
