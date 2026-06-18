from __future__ import annotations
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

from embeddings.local_embedder import LocalEmbedder as HFEmbedder

load_dotenv()

_VECTOR_QUERY = """
MATCH (chunk:KnowledgeChunk)
CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', $top_k, $vec)
YIELD node, score
WHERE node = chunk AND score >= $min_score
{country_filter}
{category_filter}
RETURN chunk.content    AS content,
       chunk.title      AS title,
       chunk.section    AS section,
       chunk.category   AS category,
       chunk.source_url AS source_url,
       chunk.country    AS country,
       chunk.tags       AS tags,
       score
ORDER BY score DESC
LIMIT $final_k
"""


class VectorRetriever:
    def __init__(self) -> None:
        self.driver = GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
        )
        self.embedder = HFEmbedder()

    def search(
        self,
        query: str,
        country: str | None = None,
        category: str | None = None,
        top_k: int = 6,
        min_score: float = 0.60,
    ) -> list[dict]:
        query_vec = self.embedder.embed_query(query)
        params: dict = {
            "top_k": top_k * 3,   # over-fetch then filter
            "vec": query_vec,
            "min_score": min_score,
            "final_k": top_k,
        }
        country_filter = ""
        category_filter = ""
        if country:
            country_filter = "AND chunk.country = $country"
            params["country"] = country
        if category:
            category_filter = "AND chunk.category = $category"
            params["category"] = category

        cypher = _VECTOR_QUERY.format(
            country_filter=country_filter,
            category_filter=category_filter,
        )
        with self.driver.session() as session:
            return session.run(cypher, **params).data()

    def close(self) -> None:
        self.driver.close()
