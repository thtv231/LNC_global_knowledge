from retrieval.neo4j_client import get_driver
from retrieval.embedder import embed_query
from graph.state import ChatState

CYPHER_VECTOR = """
CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', $top_k, $embedding)
YIELD node AS c, score
WHERE score > 0.62
  {country_filter}
RETURN c.chunk_id    AS chunk_id,
       c.content     AS content,
       c.title       AS title,
       c.category    AS category,
       c.country     AS country,
       c.source_url  AS source_url,
       coalesce(c.trust_score, 0.5) AS trust_score,
       score
ORDER BY score DESC
LIMIT $top_k
"""


def vector_retrieve(state: ChatState) -> dict:
    query = state["query"]
    country = state.get("country")
    embedding = embed_query(query)

    country_filter = "AND c.country = $country" if country else ""
    cypher = CYPHER_VECTOR.replace("{country_filter}", country_filter)

    params: dict = {"embedding": embedding, "top_k": 6}
    if country:
        params["country"] = country

    driver = get_driver()
    chunks = []
    with driver.session() as s:
        rows = s.run(cypher, **params).data()
        for r in rows:
            chunks.append({
                "chunk_id":   r["chunk_id"],
                "content":    r["content"],
                "title":      r["title"] or "",
                "category":   r["category"],
                "country":    r["country"],
                "source_url": r["source_url"] or "",
                "trust_score": r["trust_score"],
                "score":      float(r["score"]),
                "source":     "vector",
            })
    return {"vector_chunks": chunks}
