"""
Build graph relationships on top of KnowledgeChunk nodes:
  1. Category nodes  — (chunk)-[:BELONGS_TO]->(category)
  2. Site nodes      — (chunk)-[:FROM_SITE]->(site)
  3. KNN similarity  — (chunk)-[:SIMILAR_TO {score}]->(chunk)  top-3, score >= 0.80

KNN uses ThreadPoolExecutor (16 parallel Neo4j sessions) + batched MERGE writes
to avoid the 2.5-hour single-threaded bottleneck.
"""
from __future__ import annotations
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from neo4j import GraphDatabase
from tqdm import tqdm

load_dotenv()

# Suppress Neo4j deprecation-warning spam in output
logging.getLogger("neo4j").setLevel(logging.ERROR)

KNN_K     = 4     # over-fetch (includes self)
KNN_MIN   = 0.80  # minimum cosine similarity to keep edge
KNN_KEEP  = 3     # max outgoing SIMILAR_TO per node
WORKERS   = 16    # parallel Neo4j read sessions
WRITE_BATCH = 2000  # edges per UNWIND-MERGE transaction


# ── Structural relationships ─────────────────────────────────────────────────

def build_structural(session) -> None:
    print("Creating Category nodes and BELONGS_TO relationships...")
    session.run("""
        MATCH (c:KnowledgeChunk)
        WITH DISTINCT c.category AS cat, c.country AS country
        WHERE cat IS NOT NULL
        MERGE (n:Category {name: cat})
        SET n.country = country
    """)
    session.run("""
        MATCH (c:KnowledgeChunk)
        WHERE c.category IS NOT NULL
        MATCH (cat:Category {name: c.category})
        MERGE (c)-[:BELONGS_TO]->(cat)
    """)

    print("Creating Site nodes and FROM_SITE relationships...")
    session.run("""
        MATCH (c:KnowledgeChunk)
        WHERE c.site IS NOT NULL AND c.site <> ''
        WITH DISTINCT c.site AS site_name, c.country AS country
        MERGE (s:Site {name: site_name})
        SET s.country = country
    """)
    session.run("""
        MATCH (c:KnowledgeChunk)
        WHERE c.site IS NOT NULL AND c.site <> ''
        MATCH (s:Site {name: c.site})
        MERGE (c)-[:FROM_SITE]->(s)
    """)
    print("Structural relationships done.")


# ── KNN parallel build ───────────────────────────────────────────────────────

def _query_neighbors(driver, chunk_id: str) -> tuple[str, list[dict]]:
    with driver.session() as s:
        rows = s.run(
            """
            MATCH (src:KnowledgeChunk {chunk_id: $cid})
            CALL db.index.vector.queryNodes(
                'knowledge-chunk-embeddings', $k, src.embedding)
            YIELD node AS nb, score
            WHERE nb.chunk_id <> $cid AND score >= $min
            RETURN nb.chunk_id AS nb_id, score
            ORDER BY score DESC LIMIT $keep
            """,
            cid=chunk_id, k=KNN_K, min=KNN_MIN, keep=KNN_KEEP,
        ).data()
    return chunk_id, rows


def _flush_edges(driver, edges: list[dict]) -> None:
    if not edges:
        return
    with driver.session() as s:
        s.run(
            """
            UNWIND $edges AS e
            MATCH (a:KnowledgeChunk {chunk_id: e.src})
            MATCH (b:KnowledgeChunk {chunk_id: e.dst})
            MERGE (a)-[r:SIMILAR_TO]->(b)
            SET r.score = e.score
            """,
            edges=edges,
        )


def build_knn(driver) -> None:
    with driver.session() as s:
        chunk_ids = [
            r["chunk_id"]
            for r in s.run(
                "MATCH (c:KnowledgeChunk) WHERE c.embedding IS NOT NULL "
                "RETURN c.chunk_id AS chunk_id"
            ).data()
        ]

    print(f"Building KNN for {len(chunk_ids)} chunks "
          f"({WORKERS} workers, batch-write {WRITE_BATCH})...")

    pending: list[dict] = []
    lock = threading.Lock()
    total_edges = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(_query_neighbors, driver, cid): cid for cid in chunk_ids}
        with tqdm(total=len(chunk_ids), unit="chunk") as pbar:
            for fut in as_completed(futs):
                src_id, neighbors = fut.result()
                with lock:
                    for nb in neighbors:
                        pending.append({
                            "src": src_id,
                            "dst": nb["nb_id"],
                            "score": round(float(nb["score"]), 3),
                        })
                pbar.update(1)

                # flush when batch is full (check outside lock to avoid blocking)
                batch = None
                with lock:
                    if len(pending) >= WRITE_BATCH:
                        batch, pending = pending[:], []
                if batch:
                    _flush_edges(driver, batch)
                    total_edges += len(batch)

    # final flush
    _flush_edges(driver, pending)
    total_edges += len(pending)
    print(f"KNN done — {total_edges} SIMILAR_TO edges created.")


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    with driver.session() as session:
        build_structural(session)
    build_knn(driver)
    driver.close()
    print("\nGraph build complete.")


if __name__ == "__main__":
    main()
