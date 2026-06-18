"""Quick DB state checker — runs before writing test_graph_deep.py."""
from dotenv import load_dotenv; load_dotenv()
import os
from neo4j import GraphDatabase

driver = GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]))

with driver.session() as s:
    print("=== CANADA categories ===")
    for r in s.run("MATCH (c:KnowledgeChunk) WHERE c.country='canada' RETURN DISTINCT c.category AS cat, count(c) AS n ORDER BY n DESC").data():
        print(f"  {r['cat']!r:30s}  n={r['n']}")

    print("\n=== USA categories ===")
    for r in s.run("MATCH (c:KnowledgeChunk) WHERE c.country='usa' RETURN DISTINCT c.category AS cat, count(c) AS n ORDER BY n DESC").data():
        print(f"  {r['cat']!r:30s}  n={r['n']}")

    print("\n=== NZ categories (already known) ===")
    for r in s.run("MATCH (c:KnowledgeChunk) WHERE c.country='newzealand' RETURN DISTINCT c.category AS cat, count(c) AS n ORDER BY n DESC LIMIT 5").data():
        print(f"  {r['cat']!r:30s}  n={r['n']}")

    print("\n=== language values ===")
    for r in s.run("MATCH (c:KnowledgeChunk) RETURN DISTINCT c.language AS lang, count(c) AS n ORDER BY n DESC").data():
        print(f"  {r['lang']!r}  n={r['n']}")

    print("\n=== source_url null check ===")
    r = s.run("MATCH (c:KnowledgeChunk) WHERE c.source_url IS NULL RETURN count(c) AS n").single()
    print(f"  NULL source_url: {r['n']}")
    r2 = s.run("MATCH (c:KnowledgeChunk) WHERE c.source_url IS NOT NULL AND NOT c.source_url STARTS WITH 'http' RETURN count(c) AS n, collect(c.source_url)[..3] AS samples").single()
    print(f"  Non-http source_url: {r2['n']}  samples={r2['samples']}")

    print("\n=== trust_score coverage ===")
    r = s.run("MATCH (c:KnowledgeChunk) WHERE c.trust_score IS NOT NULL RETURN count(c) AS n").single()
    print(f"  Has trust_score: {r['n']}")

    print("\n=== priority coverage ===")
    for row in s.run("MATCH (c:KnowledgeChunk) WHERE c.priority IS NOT NULL RETURN c.priority AS p, count(c) AS n ORDER BY n DESC").data():
        print(f"  {row['p']!r}  n={row['n']}")

    print("\n=== BELONGS_TO coverage ===")
    total = s.run("MATCH (c:KnowledgeChunk) RETURN count(c) AS n").single()["n"]
    linked = s.run("MATCH (c:KnowledgeChunk) WHERE (c)-[:BELONGS_TO]->() RETURN count(c) AS n").single()["n"]
    print(f"  {linked}/{total} = {linked/total*100:.1f}%")

    print("\n=== Category node names ===")
    for r in s.run("MATCH (c:Category) RETURN c.name AS name, c.country AS country ORDER BY country, name").data():
        print(f"  [{r['country']}] {r['name']!r}")

driver.close()
