from __future__ import annotations

_MAX_CHARS = 6000  # ~1500 tokens — fits in Groq context


def build_context(chunks: list[dict]) -> str:
    """Assemble retrieved chunks into a formatted context string."""
    parts: list[str] = []
    total = 0
    for i, c in enumerate(chunks, 1):
        header = (
            f"[{i}] {c.get('category', '')} | {c.get('country', '').upper()} "
            f"| score={c.get('score', 0):.2f}\n"
            f"Source: {c.get('title', '')} — {c.get('source_url', '')}"
        )
        body = c.get("content", "")
        entry = f"{header}\n{body}\n"
        if total + len(entry) > _MAX_CHARS:
            break
        parts.append(entry)
        total += len(entry)
    return "\n---\n".join(parts)
