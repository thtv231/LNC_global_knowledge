"""Drop and recreate the vector index with the correct dimension from .env."""
from __future__ import annotations
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

DIM = int(os.environ.get("HF_EMBEDDING_DIM", 768))

driver = GraphDatabase.driver(
    os.environ["NEO4J_URI"],
    auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
)
with driver.session() as s:
    s.run("DROP INDEX `knowledge-chunk-embeddings` IF EXISTS")
    print("Old vector index dropped.")

    result = s.run(
        "MATCH (c:KnowledgeChunk) WHERE c.embedding IS NOT NULL "
        "SET c.embedding = NULL RETURN count(c) AS n"
    ).single()
    print(f"Cleared old embeddings on {result['n']} nodes.")

    s.run(
        f"""
        CREATE VECTOR INDEX `knowledge-chunk-embeddings`
        FOR (c:KnowledgeChunk) ON (c.embedding)
        OPTIONS {{indexConfig: {{
          `vector.dimensions`: {DIM},
          `vector.similarity_function`: 'cosine'
        }}}}
        """
    )
    print(f"New {DIM}-dim vector index created.")

driver.close()
