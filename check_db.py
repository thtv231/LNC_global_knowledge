import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
load_dotenv()
driver = GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]))
with driver.session() as s:
    chunks = s.run("MATCH (c:KnowledgeChunk) RETURN count(c) AS n").single()["n"]
    embedded = s.run("MATCH (c:KnowledgeChunk) WHERE c.embedding IS NOT NULL RETURN count(c) AS n").single()["n"]
    similar = s.run("MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) AS n").single()["n"]
    print(f"Chunks: {chunks} | Embedded: {embedded} | SIMILAR_TO: {similar}")
driver.close()
