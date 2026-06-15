from __future__ import annotations
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


def main() -> None:
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    cypher_path = Path(__file__).parent / "schema.cypher"
    statements = [s.strip() for s in cypher_path.read_text(encoding="utf-8").split(";") if s.strip()]
    with driver.session() as session:
        for stmt in statements:
            session.run(stmt)
            print(f"OK: {stmt[:80]}")
    driver.close()
    print("Schema initialised.")


if __name__ == "__main__":
    main()
