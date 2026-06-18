"""Local sentence-transformers embedder — GPU when available, CPU fallback."""
from __future__ import annotations
import os

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

_DEFAULT_MODEL = "intfloat/multilingual-e5-base"


class LocalEmbedder:
    def __init__(self) -> None:
        model_name = os.environ.get("HF_EMBEDDING_MODEL", _DEFAULT_MODEL)
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
        print(f"Loading model '{model_name}' on {device} (first run downloads ~1.1GB)...")
        self.model = SentenceTransformer(model_name, device=device)
        print(f"Model ready on {device}.")

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed document texts with E5 'passage:' prefix."""
        prefixed = [f"passage: {t}" for t in texts]
        vecs = self.model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
        return vecs.tolist()

    def embed_query(self, text: str) -> list[float]:
        """Embed a single search query with E5 'query:' prefix."""
        vec = self.model.encode([f"query: {text}"], normalize_embeddings=True, show_progress_bar=False)
        return vec[0].tolist()
