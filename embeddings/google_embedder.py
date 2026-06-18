"""Google Gemini text-embedding-004 — 768 dim, free, multilingual, no GPU needed."""
from __future__ import annotations
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

_MODEL = "text-embedding-004"
_MAX_RETRIES = 5
_RETRY_BASE = 4  # seconds, doubles each attempt
_BATCH_LIMIT = 100  # Gemini API max per request


class GoogleEmbedder:
    def __init__(self) -> None:
        self.client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        self._req_interval = 0.5
        self._last_req: float = 0.0

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed document texts (RETRIEVAL_DOCUMENT task)."""
        return self._embed(texts, task_type="RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        """Embed a single search query (RETRIEVAL_QUERY task)."""
        return self._embed([text], task_type="RETRIEVAL_QUERY")[0]

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        self._throttle()
        for attempt in range(_MAX_RETRIES):
            try:
                resp = self.client.models.embed_content(
                    model=_MODEL,
                    contents=texts,
                    config=types.EmbedContentConfig(task_type=task_type),
                )
                return [e.values for e in resp.embeddings]
            except Exception as exc:
                wait = _RETRY_BASE * (2 ** attempt)
                print(f"[Google] {exc} — retrying in {wait}s (attempt {attempt + 1}/{_MAX_RETRIES})")
                time.sleep(wait)
        raise RuntimeError(f"Google Embedding API failed after {_MAX_RETRIES} attempts")

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_req
        if elapsed < self._req_interval:
            time.sleep(self._req_interval - elapsed)
        self._last_req = time.monotonic()
