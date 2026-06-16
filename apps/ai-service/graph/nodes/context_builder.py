from graph.state import ChatState


def build_context(state: ChatState) -> dict:
    """
    Merge graph + vector + web chunks, dedup by chunk_id,
    rank: trust_score * 0.4 + similarity_score * 0.6
    Keep top 8 chunks (up to 3 can be web results).
    """
    seen: set[str] = set()
    all_chunks: list[dict] = []

    kb_chunks = state.get("graph_chunks", []) + state.get("vector_chunks", [])
    web_chunks = state.get("web_chunks", [])

    for chunk in kb_chunks + web_chunks:
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
        NOISE = ["hydrogenated oil", "contaminant", "adulterating", "hospitality", "food safety"]
        if any(kw in tl for kw in NOISE):
            return False
        return True

    all_chunks = [c for c in all_chunks if _is_valid(c)]
    # Drop KB chunks whose vector similarity is very low (likely off-topic noise)
    all_chunks = [c for c in all_chunks if c.get("is_web") or c.get("score", 0) >= 0.65 or c.get("source") == "graph"]
    all_chunks.sort(key=lambda x: x["combined_score"], reverse=True)

    # Cap web results at 3 to avoid drowning out KB knowledge
    web_kept = 0
    top: list[dict] = []
    for c in all_chunks:
        if c.get("is_web"):
            if web_kept >= 4:
                continue
            web_kept += 1
        top.append(c)
        if len(top) >= 12:
            break

    sources = []
    for c in top:
        if c.get("source_url"):
            sources.append({
                "title":      c["title"] or c.get("category") or "",
                "source_url": c["source_url"],
                "category":   c.get("category") or "",
                "country":    c.get("country") or "",
                "is_web":     bool(c.get("is_web")),
            })

    return {"merged_chunks": top, "sources": sources}
