from retrieval.neo4j_client import get_driver
from graph.state import ChatState

CYPHER_WITH_CATEGORY = """
MATCH (c:KnowledgeChunk)
WHERE c.country = $country AND c.category = $category
  AND c.embedding IS NOT NULL
WITH c LIMIT 5
OPTIONAL MATCH (c)-[r:SIMILAR_TO]->(n:KnowledgeChunk)
WHERE n.country = $country AND r.score > 0.72
WITH c,
     collect(DISTINCT {
         chunk_id: n.chunk_id,
         content:  n.content,
         title:    n.title,
         category: n.category,
         country:  n.country,
         source_url: n.source_url,
         trust_score: coalesce(n.trust_score, 0.5),
         score: r.score,
         hop: 1
     })[..3] AS neighbours
RETURN c.chunk_id    AS chunk_id,
       c.content     AS content,
       c.title       AS title,
       c.category    AS category,
       c.country     AS country,
       c.source_url  AS source_url,
       coalesce(c.trust_score, 0.5) AS trust_score,
       1.0           AS score,
       0             AS hop,
       neighbours
ORDER BY trust_score DESC
LIMIT 4
"""

CYPHER_COUNTRY_ONLY = """
MATCH (c:KnowledgeChunk)
WHERE c.country = $country AND c.embedding IS NOT NULL
WITH c ORDER BY coalesce(c.trust_score, 0.5) DESC LIMIT 3
RETURN c.chunk_id    AS chunk_id,
       c.content     AS content,
       c.title       AS title,
       c.category    AS category,
       c.country     AS country,
       c.source_url  AS source_url,
       coalesce(c.trust_score, 0.5) AS trust_score,
       1.0           AS score,
       0             AS hop,
       [] AS neighbours
"""


def graph_retrieve(state: ChatState) -> dict:
    country = state.get("country")
    category = state.get("category")
    if not country:
        return {"graph_chunks": []}

    driver = get_driver()
    chunks = []
    with driver.session() as s:
        if category:
            rows = s.run(CYPHER_WITH_CATEGORY, country=country, category=category).data()
        else:
            rows = s.run(CYPHER_COUNTRY_ONLY, country=country).data()

        for r in rows:
            chunks.append({
                "chunk_id":   r["chunk_id"],
                "content":    r["content"],
                "title":      r["title"] or "",
                "category":   r["category"],
                "country":    r["country"],
                "source_url": r["source_url"] or "",
                "trust_score": r["trust_score"],
                "score":      r["score"],
                "hop":        r["hop"],
                "source":     "graph",
            })
            for nb in (r.get("neighbours") or []):
                if nb.get("chunk_id"):
                    nb["source"] = "graph_neighbour"
                    chunks.append(nb)

    return {"graph_chunks": chunks}
