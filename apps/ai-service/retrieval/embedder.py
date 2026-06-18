from sentence_transformers import SentenceTransformer
from config import settings

_model: SentenceTransformer | None = None


def get_embedder() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_query(text: str) -> list[float]:
    """E5 yêu cầu prefix 'query: ' cho câu hỏi."""
    model = get_embedder()
    vec = model.encode(f"query: {text}", normalize_embeddings=True)
    return vec.tolist()
