from graph.state import ChatState


def build_context(state: ChatState) -> dict:
    """
    Merge graph + vector chunks, dedup theo chunk_id,
    rank: trust_score * 0.4 + similarity_score * 0.6
    Giữ tối đa 6 chunks để context không quá dài.
    """
    seen: set[str] = set()
    all_chunks: list[dict] = []

    for chunk in state.get("graph_chunks", []) + state.get("vector_chunks", []):
        cid = chunk.get("chunk_id")
        if cid and cid not in seen:
            seen.add(cid)
            combined = chunk.get("trust_score", 0.5) * 0.4 + chunk.get("score", 0.5) * 0.6
            chunk["combined_score"] = combined
            all_chunks.append(chunk)

    def _is_valid(chunk: dict) -> bool:
        title = (chunk.get("title") or "").strip()
        if not title:
            return False
        tl = title.lower()
        if "404" in tl or "error" in tl or "not found" in tl:
            return False
        # Skip food/health regulation noise unrelated to immigration
        NOISE = ["hydrogenated oil", "contaminant", "adulterating", "hospitality", "food safety"]
        if any(kw in tl for kw in NOISE):
            return False
        return True

    all_chunks = [c for c in all_chunks if _is_valid(c)]
    all_chunks.sort(key=lambda x: x["combined_score"], reverse=True)
    top = all_chunks[:6]

    sources = []
    for c in top:
        if c.get("source_url"):
            sources.append({
                "title":      c["title"] or c["category"] or "",
                "source_url": c["source_url"],
                "category":   c["category"] or "",
                "country":    c["country"] or "",
            })

    return {"merged_chunks": top, "sources": sources}
