import os
import pytest
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


@pytest.fixture(scope="session")
def driver():
    d = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    yield d
    d.close()


def run_single(driver, cypher: str, **params):
    with driver.session() as s:
        return s.run(cypher, **params).single()


def run_data(driver, cypher: str, **params):
    with driver.session() as s:
        return s.run(cypher, **params).data()


def get_sample_embedding(driver, country: str = None, category: str = None) -> list:
    clauses = ["c.embedding IS NOT NULL"]
    params = {}
    if country:
        clauses.append("c.country = $country")
        params["country"] = country
    if category:
        clauses.append("c.category = $category")
        params["category"] = category
    where = " AND ".join(clauses)
    with driver.session() as s:
        row = s.run(f"MATCH (c:KnowledgeChunk) WHERE {where} RETURN c.embedding AS emb LIMIT 1", **params).single()
    assert row is not None, f"No chunk found with: {clauses}"
    return row["emb"]
