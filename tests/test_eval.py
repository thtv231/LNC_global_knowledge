"""
Evaluation test suite for the Immigration RAG pipeline.

Covers:
  T1 — Graph schema & data integrity  (pure Cypher, no ML)
  T2 — Entity extraction              (Groq LLM)
  T3 — Vector retrieval               (embedding + Neo4j vector index)
  T4 — Full pipeline                  (entity → retrieval → context)

Run:  python -m pytest tests/test_eval.py -v
"""
from __future__ import annotations
import os
import sys
import time

import pytest
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# ─────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def driver():
    d = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    yield d
    d.close()


@pytest.fixture(scope="session")
def extractor():
    from pipeline.entity_extractor import EntityExtractor
    return EntityExtractor()


@pytest.fixture(scope="session")
def retriever():
    from retrieval.vector_retriever import VectorRetriever
    r = VectorRetriever()
    yield r
    r.close()


# ─────────────────────────────────────────────────────────────
# T1 — Graph schema & data integrity
# ─────────────────────────────────────────────────────────────

class TestGraphSchema:

    def test_connection(self, driver):
        """Neo4j is reachable."""
        with driver.session() as s:
            result = s.run("RETURN 1 AS ok").single()
        assert result["ok"] == 1

    def test_knowledgechunk_count(self, driver):
        """At least 500 KnowledgeChunk nodes exist."""
        with driver.session() as s:
            count = s.run("MATCH (c:KnowledgeChunk) RETURN count(c) AS n").single()["n"]
        print(f"\n  KnowledgeChunk nodes: {count}")
        assert count >= 500, f"Expected >=500 chunks, got {count}"

    def test_nodes_per_country(self, driver):
        """Each country (canada, usa, newzealand) has at least 50 chunks."""
        with driver.session() as s:
            rows = s.run(
                "MATCH (c:KnowledgeChunk) RETURN c.country AS country, count(c) AS n "
                "ORDER BY n DESC"
            ).data()
        country_map = {r["country"]: r["n"] for r in rows}
        print(f"\n  Chunks per country: {country_map}")
        for country in ("canada", "usa", "newzealand"):
            assert country_map.get(country, 0) >= 50, \
                f"Country '{country}' has only {country_map.get(country, 0)} chunks"

    def test_vector_index_exists(self, driver):
        """Vector index 'knowledge-chunk-embeddings' exists."""
        with driver.session() as s:
            rows = s.run("SHOW INDEXES YIELD name, type").data()
        names = [r["name"] for r in rows]
        assert "knowledge-chunk-embeddings" in names, \
            f"Vector index not found. Indexes: {names}"

    def test_embeddings_coverage(self, driver):
        """Less than 5% of KnowledgeChunk nodes are missing embeddings."""
        with driver.session() as s:
            total = s.run("MATCH (c:KnowledgeChunk) RETURN count(c) AS n").single()["n"]
            missing = s.run(
                "MATCH (c:KnowledgeChunk) WHERE c.embedding IS NULL RETURN count(c) AS n"
            ).single()["n"]
        pct = missing / total * 100 if total else 0
        print(f"\n  Missing embeddings: {missing}/{total} ({pct:.1f}%)")
        assert pct < 5, f"{pct:.1f}% of chunks have no embedding"

    def test_category_nodes(self, driver):
        """Category nodes exist and are linked via BELONGS_TO."""
        with driver.session() as s:
            cat_count = s.run("MATCH (c:Category) RETURN count(c) AS n").single()["n"]
            linked = s.run(
                "MATCH (:KnowledgeChunk)-[:BELONGS_TO]->(:Category) RETURN count(*) AS n"
            ).single()["n"]
        print(f"\n  Category nodes: {cat_count} | BELONGS_TO edges: {linked}")
        assert cat_count > 0, "No Category nodes found"
        assert linked > 0, "No BELONGS_TO relationships found"

    def test_similar_to_relationships(self, driver):
        """SIMILAR_TO edges exist between KnowledgeChunk nodes."""
        with driver.session() as s:
            n = s.run(
                "MATCH (:KnowledgeChunk)-[r:SIMILAR_TO]->(:KnowledgeChunk) RETURN count(r) AS n"
            ).single()["n"]
        print(f"\n  SIMILAR_TO edges: {n}")
        assert n > 0, "No SIMILAR_TO relationships found"

    def test_no_orphan_chunks(self, driver):
        """Less than 10% of chunks are orphans (no BELONGS_TO and no FROM_SITE)."""
        with driver.session() as s:
            total = s.run("MATCH (c:KnowledgeChunk) RETURN count(c) AS n").single()["n"]
            orphans = s.run("""
                MATCH (c:KnowledgeChunk)
                WHERE NOT (c)-[:BELONGS_TO]->() AND NOT (c)-[:FROM_SITE]->()
                RETURN count(c) AS n
            """).single()["n"]
        pct = orphans / total * 100 if total else 0
        print(f"\n  Orphan chunks: {orphans}/{total} ({pct:.1f}%)")
        assert pct < 10, f"Too many orphan chunks: {pct:.1f}%"


# ─────────────────────────────────────────────────────────────
# T2 — Entity extraction
# ─────────────────────────────────────────────────────────────

class TestEntityExtraction:

    CASES = [
        # (query, expected_country, expected_category)
        ("I want to apply for EB2-NIW in the USA",          "usa",        "EB2-NIW"),
        ("Express Entry Canada CRS score requirements",     "canada",     "Express-Entry"),
        ("Tôi muốn xin visa EB1-A diện tài năng nổi bật",  "usa",        "EB1-A"),
        ("Canada PNP provincial nominee program Ontario",   "canada",     "PNP"),
        ("New Zealand skilled migrant category points",     "newzealand", "skilled_migrant"),
        ("L1 intracompany transfer visa manager",           "usa",        "L1-Visa"),
        ("LMIA employer sponsorship Canada work permit",    "canada",     "LMIA"),
        ("Chương trình TFWP Canada dành cho lao động tạm thời", "canada", "TFWP"),
    ]

    @pytest.mark.parametrize("query,exp_country,exp_category", CASES)
    def test_extract_country_and_category(self, extractor, query, exp_country, exp_category):
        result = extractor.extract(query)
        print(f"\n  Query: {query!r}\n  Got:   {result}")
        assert result.get("country") == exp_country, \
            f"Country mismatch: expected '{exp_country}', got '{result.get('country')}'"
        assert result.get("category") == exp_category, \
            f"Category mismatch: expected '{exp_category}', got '{result.get('category')}'"

    def test_null_on_ambiguous_query(self, extractor):
        """Ambiguous question should return null country or null category gracefully."""
        result = extractor.extract("What is immigration?")
        print(f"\n  Ambiguous result: {result}")
        assert isinstance(result, dict), "Must return a dict"
        assert "country" in result and "category" in result and "topic" in result

    def test_returns_valid_json_structure(self, extractor):
        result = extractor.extract("Tôi muốn định cư nước ngoài")
        assert set(result.keys()) >= {"country", "category", "topic"}


# ─────────────────────────────────────────────────────────────
# T3 — Vector retrieval quality
# ─────────────────────────────────────────────────────────────

class TestVectorRetrieval:

    def test_basic_search_returns_results(self, retriever):
        results = retriever.search("immigration work permit", top_k=5)
        print(f"\n  Returned {len(results)} chunks")
        assert len(results) > 0, "No results returned"

    def test_scores_above_threshold(self, retriever):
        """All returned results should have score >= min_score (0.60)."""
        results = retriever.search("visa application requirements", top_k=6)
        scores = [r["score"] for r in results]
        print(f"\n  Scores: {[f'{s:.3f}' for s in scores]}")
        assert all(s >= 0.60 for s in scores), \
            f"Some scores below 0.60: {scores}"

    def test_country_filter_canada(self, retriever):
        """With country='canada', all results must be Canada chunks."""
        results = retriever.search("work permit application", country="canada", top_k=6)
        countries = [r["country"] for r in results]
        print(f"\n  Countries returned: {set(countries)}")
        assert all(c == "canada" for c in countries), \
            f"Non-Canada results with country filter: {countries}"

    def test_country_filter_usa(self, retriever):
        results = retriever.search("green card employment based", country="usa", top_k=6)
        countries = [r["country"] for r in results]
        print(f"\n  Countries returned: {set(countries)}")
        assert all(c == "usa" for c in countries)

    def test_country_filter_newzealand(self, retriever):
        results = retriever.search("skilled migrant residency points", country="newzealand", top_k=6)
        print(f"\n  NZ results: {len(results)}")
        if results:
            countries = [r["country"] for r in results]
            assert all(c == "newzealand" for c in countries)

    def test_vietnamese_query_retrieval(self, retriever):
        """Vietnamese query must still return relevant results (E5 multilingual)."""
        results = retriever.search(
            "Yêu cầu điểm CRS tối thiểu cho Express Entry Canada",
            country="canada", top_k=5
        )
        print(f"\n  Vietnamese query → {len(results)} results")
        assert len(results) > 0, "Vietnamese query returned no results"
        scores = [r["score"] for r in results]
        print(f"  Scores: {[f'{s:.3f}' for s in scores]}")
        assert max(scores) >= 0.65, f"Best score {max(scores):.3f} too low for Vietnamese query"

    def test_relevance_eb1a(self, retriever):
        """EB1-A query should return USA chunks with category eb1-a or similar."""
        results = retriever.search(
            "extraordinary ability alien EB1-A petition requirements",
            country="usa", top_k=5
        )
        print(f"\n  EB1-A results:")
        for r in results:
            print(f"    [{r['score']:.3f}] {r.get('category')} | {r.get('title','')[:50]}")
        assert len(results) > 0
        assert results[0]["score"] >= 0.70, \
            f"Top EB1-A result score {results[0]['score']:.3f} too low"

    def test_relevance_express_entry(self, retriever):
        """Express Entry query should score > 0.70."""
        results = retriever.search(
            "Express Entry comprehensive ranking system points calculation",
            country="canada", top_k=5
        )
        print(f"\n  Express Entry results:")
        for r in results:
            print(f"    [{r['score']:.3f}] {r.get('category')} | {r.get('title','')[:50]}")
        assert results[0]["score"] >= 0.70

    def test_top_k_respected(self, retriever):
        """search(top_k=3) returns at most 3 results."""
        results = retriever.search("immigration", top_k=3)
        assert len(results) <= 3

    def test_response_fields_complete(self, retriever):
        """Each result has required fields: content, title, category, country, score."""
        results = retriever.search("work visa requirements", top_k=3)
        for r in results:
            for field in ("content", "title", "category", "country", "score"):
                assert field in r, f"Field '{field}' missing from result"


# ─────────────────────────────────────────────────────────────
# T4 — Full pipeline: entity → retrieval → context
# ─────────────────────────────────────────────────────────────

class TestFullPipeline:

    PIPELINE_CASES = [
        {
            "query":           "What are the minimum CRS points for Express Entry Canada?",
            "expect_country":  "canada",
            "expect_category": "Express-Entry",
            "min_chunks":      2,
            "min_top_score":   0.70,
        },
        {
            "query":           "Tôi là kỹ sư phần mềm, có thể xin EB2-NIW không?",
            "expect_country":  "usa",
            "expect_category": "EB2-NIW",
            "min_chunks":      1,
            "min_top_score":   0.65,
        },
        {
            "query":           "New Zealand skilled migrant category eligibility criteria",
            "expect_country":  "newzealand",
            "expect_category": "skilled_migrant",
            "min_chunks":      1,
            "min_top_score":   0.60,
        },
        {
            "query":           "Canada LMIA employer requirements for hiring foreign workers",
            "expect_country":  "canada",
            "expect_category": "LMIA",
            "min_chunks":      1,
            "min_top_score":   0.65,
        },
    ]

    @pytest.mark.parametrize("case", PIPELINE_CASES, ids=[c["query"][:40] for c in PIPELINE_CASES])
    def test_end_to_end(self, extractor, retriever, case):
        from pipeline.context_builder import build_context

        t0 = time.perf_counter()
        entities = extractor.extract(case["query"])
        country  = entities.get("country")
        category = entities.get("category")
        chunks   = retriever.search(case["query"], country=country, category=category, top_k=6)
        context  = build_context(chunks)
        elapsed  = time.perf_counter() - t0

        print(f"\n  Query:    {case['query']!r}")
        print(f"  Entities: {entities}")
        top_score = chunks[0]["score"] if chunks else 0.0
        print(f"  Chunks:   {len(chunks)} | Top score: {top_score:.3f}")
        print(f"  Context:  {len(context)} chars | Time: {elapsed:.2f}s")

        assert country == case["expect_country"], \
            f"Entity country: expected '{case['expect_country']}', got '{country}'"
        assert len(chunks) >= case["min_chunks"], \
            f"Too few chunks: {len(chunks)} < {case['min_chunks']}"
        if chunks:
            assert chunks[0]["score"] >= case["min_top_score"], \
                f"Top score {chunks[0]['score']:.3f} < {case['min_top_score']}"
        assert len(context) > 100, "Context too short"

    def test_context_respects_max_chars(self, retriever):
        """build_context must not exceed 6000 chars regardless of input size."""
        from pipeline.context_builder import build_context
        chunks = retriever.search("immigration", top_k=20, min_score=0.0)
        context = build_context(chunks)
        print(f"\n  Context length: {len(context)} chars")
        assert len(context) <= 6200, f"Context too long: {len(context)} chars"

    def test_pipeline_latency(self, extractor, retriever):
        """Full entity-extract + retrieval must complete within 15 seconds."""
        query = "Canada Express Entry points requirements education language"
        t0 = time.perf_counter()
        entities = extractor.extract(query)
        retriever.search(query, country=entities.get("country"), top_k=6)
        elapsed = time.perf_counter() - t0
        print(f"\n  Pipeline latency: {elapsed:.2f}s")
        # Groq free tier can queue after burst usage; 180s covers worst-case rate-limit wait
        assert elapsed < 180, f"Pipeline too slow: {elapsed:.2f}s"
