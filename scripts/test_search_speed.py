import os, time, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from dotenv import load_dotenv; load_dotenv()

from embeddings.local_embedder import LocalEmbedder
print("Loading embedder...")
t0 = time.time()
emb = LocalEmbedder()
print(f"Embedder ready [{round(time.time()-t0,2)}s]")

print("Embedding query...")
t1 = time.time()
vec = emb.embed_query("Express Entry Canada diem toi thieu")
print(f"Embed OK [{round(time.time()-t1,2)}s]")

from neo4j import GraphDatabase
driver = GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]))
print("Running vector search...")
t2 = time.time()
cypher = (
    "CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', 18, $vec) "
    "YIELD node AS chunk, score "
    "WHERE score >= 0.60 "
    "RETURN chunk.title AS title, score "
    "ORDER BY score DESC LIMIT 6"
)
with driver.session() as s:
    result = s.run(cypher, vec=vec).data()
print(f"Vector search OK [{round(time.time()-t2,2)}s], {len(result)} results")
for r in result:
    print(f"  {r['score']:.3f} {r['title'][:60]}")
driver.close()
