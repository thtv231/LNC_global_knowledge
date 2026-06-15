"""Generate embeddings for KnowledgeChunk nodes and store them in Neo4j."""
from __future__ import annotations
import argparse
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase
from tqdm import tqdm

from .local_embedder import LocalEmbedder as HFEmbedder

load_dotenv()

DEFAULT_BATCH = 128  # GPU batch; reduce to 32 if CPU-only


def _build_text(record: dict) -> str:
    """Combine title + section + content for richer embedding context."""
    parts = [p for p in (record.get("title"), record.get("section"), record.get("content")) if p]
    return "\n".join(parts)[:2000]  # ~512 tokens max for bge-base


def embed_nodes(label: str, batch_size: int) -> None:
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    embedder = HFEmbedder()

    with driver.session() as session:
        total = session.run(
            f"MATCH (n:{label}) WHERE n.embedding IS NULL RETURN count(n) AS c"
        ).single()["c"]
        print(f"{total} {label} nodes to embed")
        if total == 0:
            driver.close()
            return

        with tqdm(total=total, unit="chunk") as pbar:
            while True:
                records = session.run(
                    f"MATCH (n:{label}) WHERE n.embedding IS NULL "
                    f"RETURN n.chunk_id AS chunk_id, "
                    f"       n.content  AS content, "
                    f"       n.title    AS title, "
                    f"       n.section  AS section "
                    f"LIMIT {batch_size}"
                ).data()
                if not records:
                    break

                texts = [_build_text(r) for r in records]
                embeddings = embedder.embed(texts)

                updates = [
                    {"chunk_id": r["chunk_id"], "emb": emb}
                    for r, emb in zip(records, embeddings)
                ]
                session.run(
                    f"UNWIND $updates AS u "
                    f"MATCH (n:{label} {{chunk_id: u.chunk_id}}) "
                    f"SET n.embedding = u.emb",
                    updates=updates,
                )
                pbar.update(len(records))

    driver.close()
    print("Embedding complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and store embeddings for Neo4j nodes")
    parser.add_argument("--label", default="KnowledgeChunk")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH)
    args = parser.parse_args()
    embed_nodes(args.label, args.batch_size)


if __name__ == "__main__":
    main()
