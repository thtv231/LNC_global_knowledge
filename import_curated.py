"""One-shot import of curated high-priority fact files into Neo4j.
Run this after json_importer and before embed_nodes when adding new curated data.
"""
import os
import sys
from pathlib import Path

# Ensure repo root on path
sys.path.insert(0, str(Path(__file__).parent))

from graph.importers.json_importer import _import_recursive, _import_flat
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

CURATED_DIR = Path(__file__).parent / "data" / "curated"

driver = GraphDatabase.driver(
    os.environ["NEO4J_URI"],
    auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
)

with driver.session() as session:
    total = _import_recursive(session, CURATED_DIR, default_country="unknown")

driver.close()
print(f"\nImported {total} curated chunks.")
print("Now run:  python -m embeddings.embed_nodes --label KnowledgeChunk --batch-size 128")
