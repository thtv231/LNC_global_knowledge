from dotenv import load_dotenv; load_dotenv()
import os
from neo4j import GraphDatabase
driver = GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]))
with driver.session() as s:
    rows = s.run("MATCH (c:KnowledgeChunk) WHERE c.country='newzealand' RETURN DISTINCT c.category AS cat, count(c) AS n ORDER BY n DESC").data()
    print("NZ categories:")
    for r in rows:
        print(f"  {r['cat']!r:30s}  n={r['n']}")
driver.close()
