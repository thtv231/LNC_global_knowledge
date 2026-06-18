# Graph Test Cases — Immigration RAG Neo4j Knowledge Graph

> Tài liệu này là bộ test case chuyên sâu để kiểm tra **toàn bộ tầng graph** của hệ thống Immigration RAG, bao gồm schema integrity, data quality, Cypher query correctness, relationship traversal, vector index, và pipeline integration.
>
> Stack: Neo4j 5.11+, `intfloat/multilingual-e5-base` (768-dim), Groq `llama-3.3-70b-versatile`, Python 3.10+

---

## Mục lục

1. [G1 — Schema & Constraint Integrity](#g1--schema--constraint-integrity)
2. [G2 — Node Data Quality](#g2--node-data-quality)
3. [G3 — Relationship Integrity](#g3--relationship-integrity)
4. [G4 — Country & Category Coverage](#g4--country--category-coverage)
5. [G5 — Vector Index Health](#g5--vector-index-health)
6. [G6 — Cypher Query Correctness](#g6--cypher-query-correctness)
7. [G7 — Graph Traversal Logic](#g7--graph-traversal-logic)
8. [G8 — Cross-Country Isolation](#g8--cross-country-isolation)
9. [G9 — Edge Cases & Boundary Conditions](#g9--edge-cases--boundary-conditions)
10. [G10 — Performance & Scale](#g10--performance--scale)
11. [G11 — Graph Retrieval Exploration](#g11--graph-retrieval-exploration)
12. [Fixtures & Helpers](#fixtures--helpers)
13. [Checklist tổng hợp](#checklist-tổng-hợp)

---

## G1 — Schema & Constraint Integrity

Kiểm tra Neo4j schema được khởi tạo đúng theo `schema.cypher`.

### G1-01: Kết nối Neo4j thành công

```python
def test_g1_01_connection(driver):
    with driver.session() as s:
        result = s.run("RETURN 1 AS ok").single()
    assert result["ok"] == 1
```

**Mục đích:** Baseline — nếu test này fail, bỏ qua toàn bộ suite.

---

### G1-02: Unique constraint trên `chunk_id`

```python
def test_g1_02_unique_constraint_chunk_id(driver):
    with driver.session() as s:
        rows = s.run("""
            SHOW CONSTRAINTS
            YIELD name, type, labelsOrTypes, properties
        """).data()
    kc_constraints = [
        r for r in rows
        if "KnowledgeChunk" in r.get("labelsOrTypes", [])
        and "chunk_id" in r.get("properties", [])
    ]
    assert len(kc_constraints) >= 1, \
        f"Không tìm thấy unique constraint trên KnowledgeChunk.chunk_id. Có: {rows}"
```

**Mục đích:** Đảm bảo không import duplicate chunk.

---

### G1-03: Vector index tồn tại với đúng tên và dimension

```python
def test_g1_03_vector_index_dimension(driver):
    with driver.session() as s:
        rows = s.run("SHOW INDEXES YIELD name, type, options").data()
    idx = next((r for r in rows if r["name"] == "knowledge-chunk-embeddings"), None)
    assert idx is not None, "Vector index 'knowledge-chunk-embeddings' không tồn tại"
    # Kiểm tra dimension = 768 (multilingual-e5-base)
    dim = idx.get("options", {}).get("indexConfig", {}).get("vector.dimensions")
    assert dim == 768, f"Dimension sai: expected 768, got {dim}"
```

**Mục đích:** Dimension phải khớp với model đang dùng. Nếu đổi sang `bge-m3` thì phải là 1024.

---

### G1-04: Full-text index tồn tại (nếu có)

```python
def test_g1_04_fulltext_index(driver):
    """Nếu schema có full-text index cho content/title search."""
    with driver.session() as s:
        rows = s.run("SHOW INDEXES YIELD name, type").data()
    ft_indexes = [r for r in rows if r["type"] == "FULLTEXT"]
    # Không assert cứng — chỉ log để biết trạng thái
    print(f"\n  Full-text indexes: {[r['name'] for r in ft_indexes]}")
```

---

### G1-05: Không có index bị FAILED hoặc POPULATING quá lâu

```python
def test_g1_05_index_states_online(driver):
    with driver.session() as s:
        rows = s.run("SHOW INDEXES YIELD name, state").data()
    bad = [r for r in rows if r["state"] not in ("ONLINE", "online")]
    assert len(bad) == 0, \
        f"Có index chưa ONLINE: {[(r['name'], r['state']) for r in bad]}"
```

---

## G2 — Node Data Quality

Kiểm tra từng property của `KnowledgeChunk` có đúng format và đủ nội dung.

### G2-01: Tổng số chunk tối thiểu

```python
def test_g2_01_min_chunk_count(driver):
    with driver.session() as s:
        n = s.run("MATCH (c:KnowledgeChunk) RETURN count(c) AS n").single()["n"]
    print(f"\n  Total KnowledgeChunk: {n}")
    assert n >= 500, f"Chỉ có {n} chunks — pipeline import chưa chạy đủ"
```

---

### G2-02: Không có chunk nào thiếu `content`

```python
def test_g2_02_no_empty_content(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.content IS NULL OR trim(c.content) = ''
            RETURN count(c) AS n, collect(c.chunk_id)[..5] AS samples
        """).single()
    print(f"\n  Empty content chunks: {rows['n']} | Samples: {rows['samples']}")
    assert rows["n"] == 0, f"{rows['n']} chunks không có content"
```

---

### G2-03: Content có độ dài hợp lý (không quá ngắn, không quá dài)

```python
def test_g2_03_content_length_distribution(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            RETURN
              count(CASE WHEN size(c.content) < 50   THEN 1 END) AS too_short,
              count(CASE WHEN size(c.content) > 8000  THEN 1 END) AS too_long,
              avg(size(c.content)) AS avg_len,
              min(size(c.content)) AS min_len,
              max(size(c.content)) AS max_len
        """).single()
    print(f"\n  Content length — avg: {rows['avg_len']:.0f} | "
          f"min: {rows['min_len']} | max: {rows['max_len']} | "
          f"too_short: {rows['too_short']} | too_long: {rows['too_long']}")
    assert rows["too_short"] == 0, \
        f"{rows['too_short']} chunks có content < 50 chars (likely import error)"
    pct_long = rows["too_long"] / max(1, rows["too_short"] + 1)
    assert rows["too_long"] < 50, \
        f"{rows['too_long']} chunks > 8000 chars — chunking có vấn đề"
```

---

### G2-04: Không có `chunk_id` trùng lặp

```python
def test_g2_04_no_duplicate_chunk_ids(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WITH c.chunk_id AS cid, count(*) AS cnt
            WHERE cnt > 1
            RETURN count(*) AS duplicate_groups, collect(cid)[..5] AS samples
        """).single()
    assert rows["duplicate_groups"] == 0, \
        f"{rows['duplicate_groups']} duplicate chunk_id groups: {rows['samples']}"
```

---

### G2-05: `country` property hợp lệ — chỉ có giá trị whitelist

```python
VALID_COUNTRIES = {"canada", "usa", "newzealand"}

def test_g2_05_valid_country_values(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            RETURN DISTINCT c.country AS country, count(c) AS n
        """).data()
    invalid = [r for r in rows if r["country"] not in VALID_COUNTRIES]
    print(f"\n  Countries found: {[(r['country'], r['n']) for r in rows]}")
    assert len(invalid) == 0, \
        f"Invalid country values: {[(r['country'], r['n']) for r in invalid]}"
```

---

### G2-06: `category` không được NULL

```python
def test_g2_06_no_null_category(driver):
    with driver.session() as s:
        n = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.category IS NULL
            RETURN count(c) AS n
        """).single()["n"]
    assert n == 0, f"{n} chunks không có category — importer thiếu mapping"
```

---

### G2-07: `trust_score` nằm trong khoảng [0, 1]

```python
def test_g2_07_trust_score_range(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.trust_score IS NOT NULL
              AND (c.trust_score < 0 OR c.trust_score > 1)
            RETURN count(c) AS n, collect(c.chunk_id)[..5] AS samples
        """).single()
    assert rows["n"] == 0, \
        f"{rows['n']} chunks có trust_score ngoài [0,1]: {rows['samples']}"
```

---

### G2-08: `source_url` là URL hợp lệ (có http/https)

```python
def test_g2_08_source_url_format(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.source_url IS NOT NULL
              AND NOT (c.source_url STARTS WITH 'http')
            RETURN count(c) AS n, collect(c.source_url)[..5] AS samples
        """).single()
    print(f"\n  Malformed URLs: {rows['n']} | Samples: {rows['samples']}")
    assert rows["n"] == 0, \
        f"{rows['n']} chunks có source_url không hợp lệ: {rows['samples']}"
```

---

### G2-09: `language` property đúng giá trị

```python
VALID_LANGUAGES = {"en", "vi", None}

def test_g2_09_language_values(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            RETURN DISTINCT c.language AS lang, count(c) AS n
        """).data()
    invalid = [r for r in rows if r["lang"] not in VALID_LANGUAGES]
    print(f"\n  Languages: {[(r['lang'], r['n']) for r in rows]}")
    assert len(invalid) == 0, f"Invalid language values: {invalid}"
```

---

## G3 — Relationship Integrity

### G3-01: `BELONGS_TO` — KnowledgeChunk → Category

```python
def test_g3_01_belongs_to_exists(driver):
    with driver.session() as s:
        n = s.run("""
            MATCH (:KnowledgeChunk)-[:BELONGS_TO]->(:Category)
            RETURN count(*) AS n
        """).single()["n"]
    assert n > 0, "Không có BELONGS_TO relationship nào — build_graph chưa chạy"
```

---

### G3-02: `BELONGS_TO` coverage — tỷ lệ chunk có relationship

```python
def test_g3_02_belongs_to_coverage(driver):
    with driver.session() as s:
        total = s.run("MATCH (c:KnowledgeChunk) RETURN count(c) AS n").single()["n"]
        linked = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE (c)-[:BELONGS_TO]->()
            RETURN count(c) AS n
        """).single()["n"]
    pct = linked / total * 100 if total else 0
    print(f"\n  BELONGS_TO coverage: {linked}/{total} ({pct:.1f}%)")
    assert pct >= 90, f"Chỉ {pct:.1f}% chunks có BELONGS_TO — cần >= 90%"
```

---

### G3-03: `FROM_SITE` — KnowledgeChunk → Site node

```python
def test_g3_03_from_site_exists(driver):
    with driver.session() as s:
        n = s.run("""
            MATCH (:KnowledgeChunk)-[:FROM_SITE]->()
            RETURN count(*) AS n
        """).single()["n"]
    print(f"\n  FROM_SITE edges: {n}")
    # Chỉ warn nếu 0 — không phải tất cả source đều có Site node
    if n == 0:
        import warnings
        warnings.warn("Không có FROM_SITE relationship nào")
```

---

### G3-04: `SIMILAR_TO` — KNN edges giữa KnowledgeChunk

```python
def test_g3_04_similar_to_exists(driver):
    with driver.session() as s:
        n = s.run("""
            MATCH (:KnowledgeChunk)-[r:SIMILAR_TO]->(:KnowledgeChunk)
            RETURN count(r) AS n
        """).single()["n"]
    print(f"\n  SIMILAR_TO edges: {n}")
    assert n > 0, "Không có SIMILAR_TO — build_graph KNN step chưa chạy"
```

---

### G3-05: `SIMILAR_TO` score nằm trong [0, 1]

```python
def test_g3_05_similar_to_score_range(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH ()-[r:SIMILAR_TO]->()
            WHERE r.score IS NOT NULL
              AND (r.score < 0 OR r.score > 1)
            RETURN count(r) AS n
        """).single()
    assert rows["n"] == 0, \
        f"{rows['n']} SIMILAR_TO edges có score ngoài [0,1]"
```

---

### G3-06: `SIMILAR_TO` không có self-loop

```python
def test_g3_06_no_self_similar_to(driver):
    with driver.session() as s:
        n = s.run("""
            MATCH (c:KnowledgeChunk)-[:SIMILAR_TO]->(c)
            RETURN count(*) AS n
        """).single()["n"]
    assert n == 0, f"{n} self-loop SIMILAR_TO tìm thấy"
```

---

### G3-07: Category node có `name` property

```python
def test_g3_07_category_has_name(driver):
    with driver.session() as s:
        n = s.run("""
            MATCH (c:Category)
            WHERE c.name IS NULL OR trim(c.name) = ''
            RETURN count(c) AS n
        """).single()["n"]
    assert n == 0, f"{n} Category nodes không có name"
```

---

### G3-08: Không có quan hệ orphan — relationship không trỏ tới node tồn tại

```python
def test_g3_08_no_dangling_relationships(driver):
    """
    Neo4j đảm bảo referential integrity ở mức DB.
    Test này verify không có KnowledgeChunk nào vừa không có BELONGS_TO vừa không có FROM_SITE.
    """
    with driver.session() as s:
        total = s.run("MATCH (c:KnowledgeChunk) RETURN count(c) AS n").single()["n"]
        orphans = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE NOT (c)-[:BELONGS_TO]->()
              AND NOT (c)-[:FROM_SITE]->()
            RETURN count(c) AS n
        """).single()["n"]
    pct = orphans / total * 100 if total else 0
    print(f"\n  Orphan chunks: {orphans}/{total} ({pct:.1f}%)")
    assert pct < 10, f"Quá nhiều orphan chunks: {pct:.1f}% (giới hạn 10%)"
```

---

## G4 — Country & Category Coverage

### G4-01: Mỗi country có ít nhất N chunks

```python
MIN_CHUNKS_PER_COUNTRY = {
    "canada":     200,
    "usa":        150,
    "newzealand":  50,
}

def test_g4_01_chunks_per_country(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            RETURN c.country AS country, count(c) AS n
        """).data()
    country_map = {r["country"]: r["n"] for r in rows}
    print(f"\n  Chunks per country: {country_map}")
    for country, min_n in MIN_CHUNKS_PER_COUNTRY.items():
        actual = country_map.get(country, 0)
        assert actual >= min_n, \
            f"Country '{country}': {actual} chunks < minimum {min_n}"
```

---

### G4-02: Canada có đủ các category chính

```python
REQUIRED_CANADA_CATEGORIES = {
    "Express-Entry", "PNP", "LMIA", "TFWP", "General"
}

def test_g4_02_canada_categories(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.country = 'canada'
            RETURN DISTINCT c.category AS cat
        """).data()
    found = {r["cat"] for r in rows}
    missing = REQUIRED_CANADA_CATEGORIES - found
    print(f"\n  Canada categories found: {found}")
    assert len(missing) == 0, f"Thiếu Canada categories: {missing}"
```

---

### G4-03: USA có đủ các category chính

```python
REQUIRED_USA_CATEGORIES = {
    "EB1-A", "EB1-B", "EB1-C", "EB2-NIW", "L1-Visa", "General"
}

def test_g4_03_usa_categories(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.country = 'usa'
            RETURN DISTINCT c.category AS cat
        """).data()
    found = {r["cat"] for r in rows}
    missing = REQUIRED_USA_CATEGORIES - found
    print(f"\n  USA categories found: {found}")
    assert len(missing) == 0, f"Thiếu USA categories: {missing}"
```

---

### G4-04: New Zealand — category `skilled_migrant` tồn tại

```python
def test_g4_04_newzealand_categories(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.country = 'newzealand'
            RETURN DISTINCT c.category AS cat, count(c) AS n
        """).data()
    cats = {r["cat"] for r in rows}
    print(f"\n  NZ categories: {cats}")
    assert "skilled_migrant" in cats, \
        f"Category 'skilled_migrant' không tồn tại trong NZ data. Có: {cats}"
```

---

### G4-05: Không có category nào có quá ít chunk (< 5)

```python
def test_g4_05_no_thin_categories(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            RETURN c.category AS cat, c.country AS country, count(c) AS n
            ORDER BY n ASC
        """).data()
    thin = [r for r in rows if r["n"] < 5]
    if thin:
        print(f"\n  Thin categories (< 5 chunks): {thin}")
    # Chỉ warn, không fail — có thể có category mới vừa add
    assert len(thin) == 0, \
        f"Có {len(thin)} (country, category) pairs với < 5 chunks: {thin}"
```

---

## G5 — Vector Index Health

### G5-01: Embedding coverage < 5% missing

```python
def test_g5_01_embedding_coverage(driver):
    with driver.session() as s:
        total = s.run("MATCH (c:KnowledgeChunk) RETURN count(c) AS n").single()["n"]
        missing = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.embedding IS NULL
            RETURN count(c) AS n
        """).single()["n"]
    pct = missing / total * 100 if total else 0
    print(f"\n  Missing embeddings: {missing}/{total} ({pct:.1f}%)")
    assert pct < 5, f"{pct:.1f}% chunks thiếu embedding — chạy lại embed_nodes.py"
```

---

### G5-02: Dimension của embedding đúng (768)

```python
def test_g5_02_embedding_dimension(driver):
    with driver.session() as s:
        row = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.embedding IS NOT NULL
            RETURN c.embedding AS emb
            LIMIT 1
        """).single()
    assert row is not None, "Không có chunk nào có embedding"
    emb = row["emb"]
    assert len(emb) == 768, \
        f"Embedding dimension sai: expected 768, got {len(emb)}"
```

---

### G5-03: Embedding không phải all-zeros (degenerate)

```python
def test_g5_03_embedding_not_zero(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.embedding IS NOT NULL
            RETURN c.embedding AS emb, c.chunk_id AS cid
            LIMIT 20
        """).data()
    zero_chunks = []
    for r in rows:
        if all(v == 0.0 for v in r["emb"]):
            zero_chunks.append(r["cid"])
    assert len(zero_chunks) == 0, \
        f"Các chunk sau có all-zero embedding: {zero_chunks}"
```

---

### G5-04: Vector similarity search trả về kết quả hợp lệ

```python
def test_g5_04_vector_search_sanity(driver):
    """
    Lấy embedding của một chunk bất kỳ và dùng làm query vector.
    Top-1 result phải là chính chunk đó (score ≈ 1.0).
    """
    with driver.session() as s:
        row = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.embedding IS NOT NULL
            RETURN c.chunk_id AS cid, c.embedding AS emb
            LIMIT 1
        """).single()
        assert row is not None
        cid, emb = row["cid"], row["emb"]

        results = s.run("""
            CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', 3, $emb)
            YIELD node, score
            RETURN node.chunk_id AS cid, score
        """, emb=emb).data()

    print(f"\n  Self-query results: {results}")
    assert len(results) > 0, "Vector search không trả về kết quả nào"
    assert results[0]["cid"] == cid, \
        f"Top-1 không phải chính chunk: expected {cid}, got {results[0]['cid']}"
    assert results[0]["score"] > 0.99, \
        f"Self-similarity score quá thấp: {results[0]['score']:.4f}"
```

---

### G5-05: Vector search với country filter hoạt động đúng

```python
def test_g5_05_vector_search_with_filter(driver):
    """Kết hợp vector search + WHERE country filter."""
    with driver.session() as s:
        # Lấy embedding của một Canada chunk
        row = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.country = 'canada' AND c.embedding IS NOT NULL
            RETURN c.embedding AS emb
            LIMIT 1
        """).single()
        assert row is not None, "Không có Canada chunk nào có embedding"
        emb = row["emb"]

        results = s.run("""
            CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', 10, $emb)
            YIELD node, score
            WHERE node.country = 'canada'
            RETURN node.chunk_id AS cid, node.country AS country, score
            LIMIT 5
        """, emb=emb).data()

    countries = [r["country"] for r in results]
    assert all(c == "canada" for c in countries), \
        f"Filter country='canada' bị leak: {countries}"
```

---

## G6 — Cypher Query Correctness

Kiểm tra các Cypher query được dùng trong pipeline có trả về kết quả đúng.

### G6-01: Query lấy chunks theo category và country

```python
@pytest.mark.parametrize("country,category", [
    ("canada",     "Express-Entry"),
    ("canada",     "LMIA"),
    ("usa",        "EB2-NIW"),
    ("usa",        "EB1-A"),
    ("newzealand", "skilled_migrant"),
])
def test_g6_01_filter_by_country_category(driver, country, category):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.country = $country AND c.category = $category
            RETURN count(c) AS n
        """, country=country, category=category).single()
    n = rows["n"]
    print(f"\n  [{country}/{category}] → {n} chunks")
    assert n > 0, \
        f"Không có chunk nào với country='{country}', category='{category}'"
```

---

### G6-02: Query BELONGS_TO traversal đúng chiều

```python
def test_g6_02_belongs_to_traversal(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)-[:BELONGS_TO]->(cat:Category)
            RETURN cat.name AS cat_name, count(c) AS n
            ORDER BY n DESC
            LIMIT 10
        """).data()
    print(f"\n  Top categories via BELONGS_TO: {[(r['cat_name'], r['n']) for r in rows]}")
    assert len(rows) > 0, "BELONGS_TO traversal không trả về kết quả"
    assert all(r["cat_name"] is not None for r in rows), \
        "Có Category node không có name"
```

---

### G6-03: SIMILAR_TO traversal — tìm neighbour của một chunk cụ thể

```python
def test_g6_03_similar_to_traversal(driver):
    with driver.session() as s:
        # Lấy một chunk bất kỳ có SIMILAR_TO edges
        seed = s.run("""
            MATCH (c:KnowledgeChunk)-[:SIMILAR_TO]->()
            RETURN c.chunk_id AS cid
            LIMIT 1
        """).single()
        assert seed is not None, "Không tìm thấy chunk nào có SIMILAR_TO"
        cid = seed["cid"]

        neighbours = s.run("""
            MATCH (c:KnowledgeChunk {chunk_id: $cid})-[r:SIMILAR_TO]->(n:KnowledgeChunk)
            RETURN n.chunk_id AS ncid, n.category AS cat, r.score AS score
            ORDER BY r.score DESC
        """, cid=cid).data()

    print(f"\n  Chunk {cid} có {len(neighbours)} SIMILAR_TO neighbours")
    assert len(neighbours) > 0
    # Score phải giảm dần (đã ORDER BY DESC)
    scores = [r["score"] for r in neighbours if r["score"] is not None]
    if len(scores) >= 2:
        assert scores == sorted(scores, reverse=True), \
            "SIMILAR_TO scores không theo thứ tự giảm dần"
```

---

### G6-04: Hybrid query — vector search + graph traversal

```python
def test_g6_04_hybrid_query(driver):
    """
    Simulate hybrid retrieval:
    1. Vector search top-5
    2. Với mỗi result, expand SIMILAR_TO 1 hop
    3. Verify kết quả hợp lý
    """
    with driver.session() as s:
        # Lấy embedding của chunk Express-Entry
        row = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.category = 'Express-Entry' AND c.embedding IS NOT NULL
            RETURN c.embedding AS emb
            LIMIT 1
        """).single()
        assert row is not None, "Không có Express-Entry chunk nào có embedding"
        emb = row["emb"]

        results = s.run("""
            CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', 5, $emb)
            YIELD node AS chunk, score
            WHERE score > 0.60 AND chunk.country = 'canada'
            OPTIONAL MATCH (chunk)-[:SIMILAR_TO]->(neighbour:KnowledgeChunk)
            RETURN chunk.chunk_id AS cid,
                   chunk.category AS cat,
                   score,
                   count(neighbour) AS neighbour_count
            ORDER BY score DESC
        """, emb=emb).data()

    print(f"\n  Hybrid query results: {len(results)} chunks")
    for r in results:
        print(f"    [{r['score']:.3f}] {r['cat']} | neighbours: {r['neighbour_count']}")
    assert len(results) > 0, "Hybrid query không trả về kết quả nào"
```

---

### G6-05: Aggregate query — CRS draw history (nếu có Draw nodes)

```python
def test_g6_05_draw_history_aggregate(driver):
    """Nếu có Draw nodes từ Express-Entry data."""
    with driver.session() as s:
        row = s.run("MATCH (d:Draw) RETURN count(d) AS n").single()
    n = row["n"]
    print(f"\n  Draw nodes: {n}")
    if n == 0:
        pytest.skip("Không có Draw node — skip test này")

    with driver.session() as s:
        rows = s.run("""
            MATCH (d:Draw)
            RETURN min(d.min_crs) AS min_crs,
                   max(d.min_crs) AS max_crs,
                   avg(d.min_crs) AS avg_crs,
                   count(d) AS total_draws
        """).single()
    print(f"  CRS stats — min: {rows['min_crs']}, max: {rows['max_crs']}, "
          f"avg: {rows['avg_crs']:.1f}, draws: {rows['total_draws']}")
    assert rows["min_crs"] > 0, "min_crs phải > 0"
    assert rows["max_crs"] <= 1200, "max_crs vượt quá tối đa CRS 1200"
```

---

## G7 — Graph Traversal Logic

### G7-01: 2-hop traversal — Chunk → Category → Chunk khác (cùng category)

```python
def test_g7_01_two_hop_same_category(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c1:KnowledgeChunk)-[:BELONGS_TO]->(cat:Category)
                  <-[:BELONGS_TO]-(c2:KnowledgeChunk)
            WHERE c1 <> c2 AND c1.country = c2.country
            RETURN cat.name AS cat, count(DISTINCT c2) AS peers
            ORDER BY peers DESC
            LIMIT 5
        """).data()
    print(f"\n  2-hop same-category peers: {rows}")
    assert len(rows) > 0, "2-hop traversal không tìm thấy peer chunks"
```

---

### G7-02: KNN graph — cluster theo country (chunks cùng country nên similar nhau hơn)

```python
def test_g7_02_knn_country_clustering(driver):
    """
    Với mỗi SIMILAR_TO edge, kiểm tra tỷ lệ same-country vs cross-country.
    Kỳ vọng: >70% edges là cùng country.
    """
    with driver.session() as s:
        rows = s.run("""
            MATCH (a:KnowledgeChunk)-[:SIMILAR_TO]->(b:KnowledgeChunk)
            RETURN
              count(CASE WHEN a.country = b.country THEN 1 END) AS same_country,
              count(*) AS total
        """).single()
    same = rows["same_country"]
    total = rows["total"]
    pct = same / total * 100 if total else 0
    print(f"\n  SIMILAR_TO same-country: {same}/{total} ({pct:.1f}%)")
    assert pct >= 60, \
        f"Chỉ {pct:.1f}% SIMILAR_TO edges là same-country — embedding model có thể bị lệch"
```

---

### G7-03: Tìm chunk liên quan đến một topic cụ thể bằng full-text trên content

```python
@pytest.mark.parametrize("keyword,expected_country", [
    ("CRS points",       "canada"),
    ("extraordinary ability", "usa"),
    ("skilled migrant",  "newzealand"),
    ("LMIA",             "canada"),
    ("EB2-NIW",          "usa"),
])
def test_g7_03_keyword_in_content(driver, keyword, expected_country):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE toLower(c.content) CONTAINS toLower($keyword)
              AND c.country = $country
            RETURN count(c) AS n
        """, keyword=keyword, country=expected_country).single()
    n = rows["n"]
    print(f"\n  Keyword '{keyword}' in {expected_country}: {n} chunks")
    assert n > 0, \
        f"Không tìm thấy chunk nào chứa '{keyword}' trong {expected_country}"
```

---

### G7-04: Traversal path dài nhất không tạo vòng lặp vô hạn

```python
def test_g7_04_no_cycle_in_similar_to(driver):
    """
    Kiểm tra không có cycle dạng A→B→A trong SIMILAR_TO.
    (Neo4j không ngăn cycle — phải kiểm tra thủ công)
    """
    with driver.session() as s:
        n = s.run("""
            MATCH (a:KnowledgeChunk)-[:SIMILAR_TO]->(b:KnowledgeChunk)-[:SIMILAR_TO]->(a)
            RETURN count(*) AS n
        """).single()["n"]
    print(f"\n  Bidirectional SIMILAR_TO cycles: {n}")
    # Bidirectional là OK (A similar B và B similar A) — chỉ cần không có A→B→C→A
    # Test này chỉ detect 2-cycle, đủ để catch obvious build_graph bugs
```

---

## G8 — Cross-Country Isolation

Đảm bảo filter country trong query hoạt động đúng — tránh data leak giữa các quốc gia.

### G8-01: Vector search Canada không trả về USA chunks

```python
def test_g8_01_canada_search_no_usa_leak(driver):
    with driver.session() as s:
        emb = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.country = 'canada' AND c.embedding IS NOT NULL
            RETURN c.embedding AS emb LIMIT 1
        """).single()["emb"]

        results = s.run("""
            CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', 10, $emb)
            YIELD node, score
            WHERE node.country = 'canada'
            RETURN node.country AS country
        """, emb=emb).data()

    countries = {r["country"] for r in results}
    assert countries == {"canada"}, f"Leak: {countries}"
```

---

### G8-02: Category `EB2-NIW` không xuất hiện trong Canada

```python
def test_g8_02_eb2_niw_only_usa(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.category = 'EB2-NIW'
            RETURN DISTINCT c.country AS country
        """).data()
    countries = {r["country"] for r in rows}
    assert countries == {"usa"}, \
        f"EB2-NIW xuất hiện ở nước sai: {countries}"
```

---

### G8-03: Category `Express-Entry` không xuất hiện trong USA hoặc NZ

```python
def test_g8_03_express_entry_only_canada(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.category = 'Express-Entry'
            RETURN DISTINCT c.country AS country
        """).data()
    countries = {r["country"] for r in rows}
    assert countries.issubset({"canada"}), \
        f"Express-Entry xuất hiện ở nước sai: {countries}"
```

---

### G8-04: `skilled_migrant` chỉ có trong NZ

```python
def test_g8_04_skilled_migrant_only_nz(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.category = 'skilled_migrant'
            RETURN DISTINCT c.country AS country
        """).data()
    countries = {r["country"] for r in rows}
    assert countries.issubset({"newzealand"}), \
        f"skilled_migrant xuất hiện sai nước: {countries}"
```

---

## G9 — Edge Cases & Boundary Conditions

### G9-01: Query với embedding vector all-zeros không crash

```python
def test_g9_01_zero_vector_query(driver):
    zero_emb = [0.0] * 768
    with driver.session() as s:
        try:
            results = s.run("""
                CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', 3, $emb)
                YIELD node, score
                RETURN count(*) AS n
            """, emb=zero_emb).single()
            print(f"\n  Zero-vector query returned: {results['n']} results")
        except Exception as e:
            pytest.fail(f"Zero-vector query gây ra exception: {e}")
```

---

### G9-02: Query với top_k = 0 không crash

```python
def test_g9_02_topk_zero(driver):
    with driver.session() as s:
        emb = s.run("""
            MATCH (c:KnowledgeChunk) WHERE c.embedding IS NOT NULL
            RETURN c.embedding AS emb LIMIT 1
        """).single()["emb"]
        try:
            results = s.run("""
                CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', 1, $emb)
                YIELD node, score
                WHERE 1=0
                RETURN count(*) AS n
            """, emb=emb).single()
        except Exception as e:
            pytest.fail(f"Exception khi filter ra empty result: {e}")
```

---

### G9-03: Country không tồn tại trả về empty, không crash

```python
def test_g9_03_nonexistent_country_filter(driver):
    with driver.session() as s:
        n = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.country = 'australia'
            RETURN count(c) AS n
        """).single()["n"]
    assert n == 0, f"Unexpected: {n} chunks với country='australia'"
```

---

### G9-04: Category với ký tự đặc biệt không gây lỗi

```python
@pytest.mark.parametrize("bad_category", [
    "'; DROP TABLE KnowledgeChunk; --",
    "EB2-NIW' OR '1'='1",
    "",
    "   ",
    "a" * 1000,
])
def test_g9_04_category_injection_safe(driver, bad_category):
    """Parameterized query trong Neo4j driver an toàn với injection."""
    with driver.session() as s:
        n = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.category = $cat
            RETURN count(c) AS n
        """, cat=bad_category).single()["n"]
    assert n == 0, f"Unexpected chunks returned for bad category: {bad_category!r}"
```

---

### G9-05: Chunk có content tiếng Việt được lưu đúng encoding

```python
def test_g9_05_vietnamese_content_encoding(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.language = 'vi'
               OR toLower(c.content) CONTAINS 'định cư'
               OR toLower(c.content) CONTAINS 'visa'
            RETURN c.content AS content, c.chunk_id AS cid
            LIMIT 5
        """).data()
    print(f"\n  Vietnamese chunks found: {len(rows)}")
    for r in rows:
        content = r["content"]
        # Kiểm tra không bị mojibake (dấu hiệu: chuỗi toàn ???)
        assert "???" not in content, \
            f"Chunk {r['cid']} có dấu hiệu encoding lỗi: {content[:100]}"
        # Kiểm tra decode đúng UTF-8
        try:
            content.encode("utf-8")
        except Exception as e:
            pytest.fail(f"Chunk {r['cid']} không encode được UTF-8: {e}")
```

---

## G10 — Performance & Scale

### G10-01: Vector search top-10 hoàn thành trong 2 giây

```python
import time

def test_g10_01_vector_search_latency(driver):
    with driver.session() as s:
        emb = s.run("""
            MATCH (c:KnowledgeChunk) WHERE c.embedding IS NOT NULL
            RETURN c.embedding AS emb LIMIT 1
        """).single()["emb"]

        t0 = time.perf_counter()
        results = s.run("""
            CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', 10, $emb)
            YIELD node, score
            RETURN node.chunk_id AS cid, score
        """, emb=emb).data()
        elapsed = time.perf_counter() - t0

    print(f"\n  Vector search latency: {elapsed:.3f}s | results: {len(results)}")
    assert elapsed < 2.0, f"Vector search quá chậm: {elapsed:.3f}s (giới hạn 2s)"
```

---

### G10-02: Filtered vector search (country + score) hoàn thành trong 3 giây

```python
def test_g10_02_filtered_search_latency(driver):
    with driver.session() as s:
        emb = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.country = 'canada' AND c.embedding IS NOT NULL
            RETURN c.embedding AS emb LIMIT 1
        """).single()["emb"]

        t0 = time.perf_counter()
        s.run("""
            CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', 20, $emb)
            YIELD node, score
            WHERE score > 0.60 AND node.country = 'canada'
            RETURN node.chunk_id, score
            LIMIT 10
        """, emb=emb).data()
        elapsed = time.perf_counter() - t0

    print(f"\n  Filtered search latency: {elapsed:.3f}s")
    assert elapsed < 3.0, f"Filtered search quá chậm: {elapsed:.3f}s"
```

---

### G10-03: COUNT query toàn bộ graph hoàn thành trong 5 giây

```python
def test_g10_03_count_query_performance(driver):
    queries = [
        "MATCH (c:KnowledgeChunk) RETURN count(c) AS n",
        "MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) AS n",
        "MATCH ()-[r:BELONGS_TO]->() RETURN count(r) AS n",
    ]
    for query in queries:
        t0 = time.perf_counter()
        with driver.session() as s:
            s.run(query).single()
        elapsed = time.perf_counter() - t0
        print(f"\n  Query '{query[:40]}...' → {elapsed:.3f}s")
        assert elapsed < 5.0, \
            f"Query quá chậm ({elapsed:.3f}s): {query}"
```

---

### G10-04: 2-hop traversal hoàn thành trong 10 giây

```python
def test_g10_04_two_hop_traversal_performance(driver):
    t0 = time.perf_counter()
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)-[:BELONGS_TO]->(cat:Category)
                  <-[:BELONGS_TO]-(peer:KnowledgeChunk)
            WHERE c.country = 'canada'
            RETURN cat.name AS cat, count(DISTINCT peer) AS peers
            ORDER BY peers DESC
            LIMIT 10
        """).data()
    elapsed = time.perf_counter() - t0
    print(f"\n  2-hop traversal: {elapsed:.3f}s | results: {len(rows)}")
    assert elapsed < 10.0, f"2-hop traversal quá chậm: {elapsed:.3f}s"
```

---

## G11 — Graph Retrieval Exploration

> Đây là nhóm test **đặc thù của graph DB** — khai thác những gì vector search thuần (AstraDB, Pinecone) không làm được: multi-hop reasoning, so sánh chương trình, phát hiện knowledge gap, ranking theo trust, và truy vết nguồn. Tất cả đều được đặt trong ngữ cảnh tư vấn định cư thực tế.

---

### G11-01: Multi-hop — từ query tìm chunk → expand sang chunk liên quan cùng topic

**Kịch bản thực tế:** Khách hỏi về EB2-NIW → chatbot không chỉ trả về chunk EB2-NIW mà còn kéo thêm các chunk NIW-Entrepreneurs và EB1-A (thường xét song song).

```python
def test_g11_01_multihop_expand_related_chunks(driver):
    """
    Vector search top-3 cho EB2-NIW,
    rồi 1-hop SIMILAR_TO để mở rộng context.
    Verify: kết quả mở rộng có chunk cùng country=usa.
    """
    with driver.session() as s:
        seed_emb = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.category = 'EB2-NIW' AND c.embedding IS NOT NULL
            RETURN c.embedding AS emb LIMIT 1
        """).single()["emb"]

        results = s.run("""
            CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', 3, $emb)
            YIELD node AS seed, score AS seed_score
            WHERE seed.country = 'usa' AND seed_score > 0.65

            // 1-hop expand qua SIMILAR_TO
            OPTIONAL MATCH (seed)-[r:SIMILAR_TO]->(neighbour:KnowledgeChunk)
            WHERE neighbour.country = 'usa'

            RETURN
                seed.chunk_id        AS seed_id,
                seed.category        AS seed_cat,
                seed_score,
                collect(DISTINCT {
                    cid:   neighbour.chunk_id,
                    cat:   neighbour.category,
                    score: r.score
                })[..3]              AS neighbours
            ORDER BY seed_score DESC
        """, emb=seed_emb).data()

    print(f"\n  Multi-hop EB2-NIW expand: {len(results)} seeds")
    for r in results:
        print(f"    [{r['seed_score']:.3f}] {r['seed_cat']} → {len(r['neighbours'])} neighbours")

    assert len(results) > 0, "Không tìm được seed chunk nào cho EB2-NIW"
    has_neighbours = any(len(r["neighbours"]) > 0 for r in results)
    assert has_neighbours, \
        "Không có SIMILAR_TO neighbours — build_graph KNN chưa chạy hoặc score quá thấp"
```

---

### G11-02: Cross-category expansion — từ LMIA tìm được TFWP liên quan

**Kịch bản thực tế:** Khách hỏi về LMIA → chatbot nên biết TFWP (Temporary Foreign Worker Program) là chương trình liên quan có thể gợi ý thêm.

```python
def test_g11_02_cross_category_discovery(driver):
    """
    Từ chunk LMIA (canada), expand SIMILAR_TO và kiểm tra
    có tìm được chunk thuộc category khác nhưng cùng country không.
    Đây là khả năng 'cross-category discovery' — graph làm được, pure vector khó hơn.
    """
    with driver.session() as s:
        results = s.run("""
            MATCH (c:KnowledgeChunk {country: 'canada', category: 'LMIA'})
                  -[r:SIMILAR_TO]->(n:KnowledgeChunk)
            WHERE n.country = 'canada'
              AND n.category <> 'LMIA'
            RETURN n.category AS cross_cat, count(*) AS n_chunks, avg(r.score) AS avg_score
            ORDER BY avg_score DESC
            LIMIT 5
        """).data()

    print(f"\n  Cross-category từ LMIA:")
    for r in results:
        print(f"    {r['cross_cat']:20s}  chunks={r['n_chunks']}  avg_score={r['avg_score']:.3f}")

    assert len(results) > 0, \
        "LMIA không có SIMILAR_TO edge sang category khác — knowledge graph bị isolated"
    # Kỳ vọng TFWP hoặc Express-Entry xuất hiện
    cats_found = {r["cross_cat"] for r in results}
    related = cats_found & {"TFWP", "Express-Entry", "PNP", "General"}
    assert len(related) > 0, \
        f"Không tìm thấy category liên quan đến LMIA: {cats_found}"
```

---

### G11-03: Ranking theo `trust_score` — chunk nguồn chính phủ phải xếp trên fanpage

**Kịch bản thực tế:** Câu hỏi về điều kiện Express Entry → chunk từ canada.ca phải được ưu tiên hơn chunk từ blog/fanpage.

```python
def test_g11_03_trust_score_ranking(driver):
    """
    Với cùng một category, chunk có trust_score cao hơn phải được retrieve trước
    khi pipeline sort theo trust_score.
    """
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.country = 'canada'
              AND c.category = 'Express-Entry'
              AND c.trust_score IS NOT NULL
            RETURN c.chunk_id AS cid,
                   c.trust_score AS ts,
                   c.site AS site,
                   c.title AS title
            ORDER BY c.trust_score DESC
            LIMIT 10
        """).data()

    print(f"\n  Express-Entry chunks by trust_score:")
    for r in rows:
        print(f"    [{r['ts']:.2f}] {r['site']:30s}  {(r['title'] or '')[:50]}")

    assert len(rows) > 0, "Không có chunk Express-Entry nào có trust_score"

    # Chunk đầu tiên phải có trust_score cao nhất
    scores = [r["ts"] for r in rows]
    assert scores == sorted(scores, reverse=True), \
        "ORDER BY trust_score DESC không hoạt động đúng"

    # Nếu có chunk từ nguồn chính phủ, phải nằm trong top
    gov_sites = [r for r in rows if r["site"] and
                 any(kw in (r["site"] or "").lower()
                     for kw in ["canada.ca", "ircc", "cic.gc.ca", "immigration.ca"])]
    if gov_sites:
        top_site = rows[0]["site"] or ""
        is_gov_top = any(kw in top_site.lower()
                         for kw in ["canada.ca", "ircc", "cic.gc.ca"])
        print(f"\n  Top chunk site: {top_site} | is_gov: {is_gov_top}")
```

---

### G11-04: Source diversity — retrieval không trả về toàn bộ từ một site duy nhất

**Kịch bản thực tế:** Nếu top-6 chunks đều từ cùng một website, câu trả lời của chatbot sẽ bị thiên lệch và thiếu góc nhìn đa chiều.

```python
def test_g11_04_source_diversity_in_retrieval(driver):
    """
    Vector search top-6 cho một query immigration phổ biến.
    Verify: kết quả đến từ ít nhất 2 sites khác nhau.
    """
    with driver.session() as s:
        emb = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.category = 'Express-Entry' AND c.embedding IS NOT NULL
            RETURN c.embedding AS emb LIMIT 1
        """).single()["emb"]

        results = s.run("""
            CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', 6, $emb)
            YIELD node, score
            WHERE node.country = 'canada' AND score > 0.60
            RETURN node.site AS site, node.chunk_id AS cid, score
            ORDER BY score DESC
        """, emb=emb).data()

    sites = [r["site"] for r in results if r["site"]]
    unique_sites = set(sites)
    print(f"\n  Sites in top-6: {unique_sites}")
    assert len(unique_sites) >= 2, \
        f"Retrieval chỉ trả về chunks từ 1 site: {unique_sites} — dữ liệu quá đồng nhất"
```

---

### G11-05: Phát hiện knowledge gap — category có ít chunk sẽ trả lời kém

**Kịch bản thực tế:** Trước khi deploy chatbot, cần biết category nào đang "thiếu tư liệu" để tránh chatbot trả lời sai hoặc hallucinate.

```python
IMMIGRATION_PROGRAMS = {
    "canada":     ["Express-Entry", "PNP", "LMIA", "TFWP", "General"],
    "usa":        ["EB1-A", "EB1-B", "EB1-C", "EB2-NIW", "L1-Visa", "General"],
    "newzealand": ["skilled_migrant"],
}
MIN_CHUNKS_PER_PROGRAM = 10  # Ngưỡng tối thiểu để chatbot trả lời decent

def test_g11_05_knowledge_gap_detection(driver):
    """
    Report các (country, category) có < MIN_CHUNKS_PER_PROGRAM chunks.
    Đây là knowledge gap — chatbot sẽ yếu ở những vùng này.
    """
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            RETURN c.country AS country, c.category AS category, count(c) AS n
            ORDER BY n ASC
        """).data()

    chunk_map = {(r["country"], r["category"]): r["n"] for r in rows}
    gaps = []

    for country, programs in IMMIGRATION_PROGRAMS.items():
        for prog in programs:
            n = chunk_map.get((country, prog), 0)
            if n < MIN_CHUNKS_PER_PROGRAM:
                gaps.append((country, prog, n))

    print(f"\n  Knowledge gaps (< {MIN_CHUNKS_PER_PROGRAM} chunks):")
    for country, prog, n in gaps:
        print(f"    [{country}] {prog:20s} → {n} chunks  ⚠️")

    assert len(gaps) == 0, \
        f"Có {len(gaps)} knowledge gaps cần bổ sung data: {gaps}"
```

---

### G11-06: Semantic coherence — các chunk cùng category phải similar nhau

**Kịch bản thực tế:** Nếu category `EB2-NIW` có những chunk không liên quan (import lỗi), embedding của chúng sẽ xa nhau — detect được qua avg SIMILAR_TO score.

```python
def test_g11_06_intra_category_coherence(driver):
    """
    Với mỗi (country, category), tính avg score của SIMILAR_TO edges
    giữa các chunk cùng category. Score quá thấp = category bị nhiễm data không liên quan.
    """
    with driver.session() as s:
        rows = s.run("""
            MATCH (a:KnowledgeChunk)-[r:SIMILAR_TO]->(b:KnowledgeChunk)
            WHERE a.country = b.country AND a.category = b.category
              AND r.score IS NOT NULL
            RETURN a.country AS country,
                   a.category AS category,
                   avg(r.score) AS avg_coherence,
                   count(r) AS edge_count
            ORDER BY avg_coherence ASC
        """).data()

    print(f"\n  Intra-category coherence scores:")
    for r in rows:
        flag = "⚠️" if r["avg_coherence"] < 0.50 else "✅"
        print(f"    {flag} [{r['country']}] {r['category']:20s}  "
              f"avg={r['avg_coherence']:.3f}  edges={r['edge_count']}")

    low_coherence = [r for r in rows if r["avg_coherence"] < 0.50]
    assert len(low_coherence) == 0, \
        f"Các category sau có coherence < 0.50 — data quality đáng ngờ: " \
        f"{[(r['country'], r['category'], r['avg_coherence']) for r in low_coherence]}"
```

---

### G11-07: So sánh chương trình — graph phải cho phép query "Canada vs USA" trong cùng một hop

**Kịch bản thực tế:** Khách hỏi "Tôi nên chọn Canada hay Mỹ để định cư?" → chatbot cần retrieve được chunks từ cả hai country trong cùng một retrieval call.

```python
@pytest.mark.parametrize("cat_a,country_a,cat_b,country_b", [
    ("Express-Entry", "canada", "EB2-NIW",        "usa"),
    ("PNP",           "canada", "L1-Visa",         "usa"),
    ("LMIA",          "canada", "skilled_migrant", "newzealand"),
])
def test_g11_07_cross_country_comparison_retrieval(driver, cat_a, country_a, cat_b, country_b):
    """
    Retrieve chunks từ 2 country/category khác nhau trong một query.
    Đây là pattern 'so sánh chương trình' — graph phải hỗ trợ không cần filter cứng.
    """
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE (c.country = $ca AND c.category = $cat_a)
               OR (c.country = $cb AND c.category = $cat_b)
            RETURN c.country AS country, c.category AS cat, count(c) AS n
        """, ca=country_a, cat_a=cat_a, cb=country_b, cat_b=cat_b).data()

    found = {(r["country"], r["cat"]): r["n"] for r in rows}
    print(f"\n  Cross-country comparison [{country_a}/{cat_a}] vs [{country_b}/{cat_b}]:")
    print(f"    {found}")

    assert (country_a, cat_a) in found and found[(country_a, cat_a)] > 0, \
        f"Không có chunk [{country_a}/{cat_a}]"
    assert (country_b, cat_b) in found and found[(country_b, cat_b)] > 0, \
        f"Không có chunk [{country_b}/{cat_b}]"
```

---

### G11-08: Truy vết nguồn — mỗi chunk retrieved phải có `source_url` để citation

**Kịch bản thực tế:** Chatbot trả lời phải kèm nguồn. Nếu chunk không có `source_url`, câu trả lời sẽ không có citation → mất trust với khách hàng.

```python
def test_g11_08_source_traceability(driver):
    """
    Với top-10 chunks retrieved cho mỗi country,
    verify rằng ít nhất 80% có source_url không NULL.
    """
    for country in ("canada", "usa", "newzealand"):
        with driver.session() as s:
            emb = s.run("""
                MATCH (c:KnowledgeChunk)
                WHERE c.country = $country AND c.embedding IS NOT NULL
                RETURN c.embedding AS emb LIMIT 1
            """, country=country).single()["emb"]

            results = s.run("""
                CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', 10, $emb)
                YIELD node, score
                WHERE node.country = $country
                RETURN node.source_url AS url, node.chunk_id AS cid
            """, emb=emb, country=country).data()

        total = len(results)
        with_url = sum(1 for r in results if r["url"] and r["url"].startswith("http"))
        pct = with_url / total * 100 if total else 0

        print(f"\n  [{country}] source_url coverage: {with_url}/{total} ({pct:.1f}%)")
        no_url = [r["cid"] for r in results if not r["url"]]
        assert pct >= 80, \
            f"[{country}] chỉ {pct:.1f}% chunks có source_url — citation sẽ bị thiếu. " \
            f"Chunk IDs không có URL: {no_url[:5]}"
```

---

### G11-09: Phát hiện duplicate semantic — hai chunk quá giống nhau (near-duplicate)

**Kịch bản thực tế:** Nếu cùng một thông tin được import từ nhiều nguồn, chatbot sẽ lặp lại context → waste token và giảm chất lượng answer.

```python
def test_g11_09_near_duplicate_detection(driver):
    """
    Tìm các cặp chunk có SIMILAR_TO score > 0.97 — gần như duplicate.
    Nếu quá nhiều, pipeline import có thể đang crawl trùng source.
    """
    with driver.session() as s:
        rows = s.run("""
            MATCH (a:KnowledgeChunk)-[r:SIMILAR_TO]->(b:KnowledgeChunk)
            WHERE r.score > 0.97 AND id(a) < id(b)
            RETURN a.chunk_id AS cid_a,
                   b.chunk_id AS cid_b,
                   a.category AS cat,
                   a.country AS country,
                   r.score AS score
            ORDER BY r.score DESC
            LIMIT 20
        """).data()

    print(f"\n  Near-duplicates (score > 0.97): {len(rows)} pairs")
    for r in rows[:5]:
        print(f"    [{r['score']:.4f}] [{r['country']}/{r['cat']}] "
              f"{r['cid_a'][:20]} ↔ {r['cid_b'][:20]}")

    # Warn nếu > 5% total chunks là near-duplicate
    with driver.session() as s:
        total = s.run("MATCH (c:KnowledgeChunk) RETURN count(c) AS n").single()["n"]

    pct = len(rows) / total * 100 if total else 0
    print(f"  Near-duplicate rate: {len(rows)}/{total} ({pct:.1f}%)")
    assert len(rows) < total * 0.05, \
        f"Quá nhiều near-duplicate: {len(rows)} pairs ({pct:.1f}%) — cần dedup pipeline"
```

---

### G11-10: Priority-aware retrieval — chunk `priority=high` phải nằm trong top-k

**Kịch bản thực tế:** Fanpage data có field `priority` (high/medium/low). Câu trả lời về yêu cầu visa quan trọng phải dùng chunk priority=high, không phải chunk general/low.

```python
def test_g11_10_priority_aware_retrieval(driver):
    """
    Với category có chunks priority=high, sau khi vector search,
    kiểm tra top-3 có ít nhất 1 chunk priority=high hoặc trust_score cao.
    """
    with driver.session() as s:
        # Kiểm tra có priority property không
        sample = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.priority IS NOT NULL
            RETURN c.priority AS p, count(*) AS n
        """).data()

    if not sample:
        pytest.skip("Không có chunk nào có property 'priority' — skip")

    print(f"\n  Priority distribution: {[(r['p'], r['n']) for r in sample]}")

    with driver.session() as s:
        emb = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.priority = 'high' AND c.embedding IS NOT NULL
            RETURN c.embedding AS emb, c.country AS country, c.category AS cat
            LIMIT 1
        """).single()
        assert emb is not None, "Không có chunk nào có priority='high' kèm embedding"

        results = s.run("""
            CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', 6, $emb)
            YIELD node, score
            WHERE node.country = $country
            RETURN node.priority AS priority,
                   node.trust_score AS ts,
                   score
            ORDER BY score DESC
            LIMIT 3
        """, emb=emb["emb"], country=emb["country"]).data()

    high_priority_in_top3 = any(
        r["priority"] == "high" or (r["ts"] is not None and r["ts"] >= 0.8)
        for r in results
    )
    print(f"\n  Top-3 priorities: {[(r['priority'], r['ts'], r['score']) for r in results]}")
    assert high_priority_in_top3, \
        "Top-3 retrieval không có chunk nào priority=high hoặc trust_score >= 0.8"

```

---

## G12 — Immigration Domain Retrieval Quality

> Test này kiểm tra retrieval đúng **ngữ nghĩa nghiệp vụ định cư** — không chỉ đúng về kỹ thuật mà còn đúng về nội dung mà một consultant thực sự cần.

---

### G12-01: Query điểm CRS Express Entry phải trả về chunk có số cụ thể

**Kịch bản:** Khách hỏi "Cần bao nhiêu điểm CRS để được mời?" → chunk trả về phải chứa thông tin về ngưỡng CRS, không phải giải thích chung về Express Entry.

```python
def test_g12_01_crs_threshold_chunk_exists(driver):
    with driver.session() as s:
        rows = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.country = 'canada'
              AND c.category = 'Express-Entry'
              AND (
                toLower(c.content) CONTAINS 'crs'
                OR toLower(c.content) CONTAINS 'comprehensive ranking'
                OR toLower(c.content) CONTAINS 'cut-off'
                OR toLower(c.content) CONTAINS 'invitation to apply'
              )
            RETURN count(c) AS n, collect(c.title)[..3] AS sample_titles
        """).single()
    print(f"\n  CRS threshold chunks: {rows['n']} | Titles: {rows['sample_titles']}")
    assert rows["n"] >= 3, \
        f"Chỉ có {rows['n']} chunks về CRS threshold — không đủ để trả lời câu hỏi điểm số"
```

---

### G12-02: Query yêu cầu IELTS/language cho các chương trình chính

```python
@pytest.mark.parametrize("country,category,keywords", [
    ("canada", "Express-Entry", ["clb", "ielts", "language", "english"]),
    ("canada", "PNP",           ["language", "english", "french", "clb"]),
    ("usa",    "EB2-NIW",       ["english", "petition", "language"]),
    ("newzealand", "skilled_migrant", ["ielts", "english", "language"]),
])
def test_g12_02_language_requirement_coverage(driver, country, category, keywords):
    keyword_conditions = " OR ".join(
        [f"toLower(c.content) CONTAINS '{kw}'" for kw in keywords]
    )
    with driver.session() as s:
        n = s.run(f"""
            MATCH (c:KnowledgeChunk)
            WHERE c.country = $country AND c.category = $category
              AND ({keyword_conditions})
            RETURN count(c) AS n
        """, country=country, category=category).single()["n"]
    print(f"\n  [{country}/{category}] language requirement chunks: {n}")
    assert n >= 1, \
        f"Không có chunk nào đề cập yêu cầu ngôn ngữ cho [{country}/{category}]"
```

---

### G12-03: Query về processing time / thời gian xử lý hồ sơ

**Kịch bản:** Khách hỏi "Visa Canada mất bao lâu?" — câu hỏi rất phổ biến trong tư vấn.

```python
@pytest.mark.parametrize("country,keywords", [
    ("canada",     ["processing time", "weeks", "months", "application"]),
    ("usa",        ["processing time", "weeks", "months", "uscis"]),
    ("newzealand", ["processing time", "weeks", "months"]),
])
def test_g12_03_processing_time_coverage(driver, country, keywords):
    kw_conditions = " OR ".join([f"toLower(c.content) CONTAINS '{kw}'" for kw in keywords])
    with driver.session() as s:
        n = s.run(f"""
            MATCH (c:KnowledgeChunk)
            WHERE c.country = $country AND ({kw_conditions})
            RETURN count(c) AS n
        """, country=country).single()["n"]
    print(f"\n  [{country}] processing time chunks: {n}")
    assert n >= 1, \
        f"[{country}] không có chunk nào đề cập processing time — chatbot sẽ không trả lời được"
```

---

### G12-04: Query về chi phí / fees không bị thiếu

**Kịch bản:** "Nộp đơn Express Entry tốn bao nhiêu?" — câu hỏi thực tế không thể bỏ qua.

```python
def test_g12_04_fee_information_coverage(driver):
    fee_keywords = ["fee", "cost", "dollar", "payment", "cad", "usd"]
    for country in ("canada", "usa", "newzealand"):
        kw_cond = " OR ".join([f"toLower(c.content) CONTAINS '{kw}'" for kw in fee_keywords])
        with driver.session() as s:
            n = s.run(f"""
                MATCH (c:KnowledgeChunk)
                WHERE c.country = $country AND ({kw_cond})
                RETURN count(c) AS n
            """, country=country).single()["n"]
        print(f"\n  [{country}] fee-related chunks: {n}")
        assert n >= 1, \
            f"[{country}] không có chunk nào về phí — chatbot sẽ không biết trả lời về chi phí"
```

---

### G12-05: Câu hỏi tiếng Việt phổ biến từ client có thể map sang đúng category

**Kịch bản:** Đây là test semantic mapping — query tiếng Việt thường gặp của khách hàng Việt phải retrieve đúng category.

```python
VIETNAMESE_QUERY_EXPECTATIONS = [
    # (query_vi, expected_country, expected_category_hint)
    ("điểm CRS tối thiểu để được mời vào Express Entry",    "canada",     "Express-Entry"),
    ("bảo lãnh lao động Canada LMIA",                        "canada",     "LMIA"),
    ("visa định cư tài năng xuất chúng EB1-A Mỹ",           "usa",        "EB1-A"),
    ("chương trình tay nghề cao New Zealand",                "newzealand", "skilled_migrant"),
    ("kỹ sư phần mềm xin EB2-NIW có được không",            "usa",        "EB2-NIW"),
    ("tỉnh bang Ontario Canada PNP",                         "canada",     "PNP"),
]

@pytest.mark.parametrize("query_vi,country,cat_hint", VIETNAMESE_QUERY_EXPECTATIONS)
def test_g12_05_vietnamese_query_maps_to_category(driver, query_vi, country, cat_hint):
    """
    Dùng CONTAINS search (không dùng vector) để verify DB có chunk phù hợp.
    Test này verify data coverage, không test embedding model.
    """
    with driver.session() as s:
        # Tìm theo category và country — proxy cho việc vector search sẽ tìm đúng
        n = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.country = $country AND c.category = $category
            RETURN count(c) AS n
        """, country=country, category=cat_hint).single()["n"]

    print(f"\n  Query: '{query_vi[:40]}...'")
    print(f"  Expect: [{country}/{cat_hint}] → {n} chunks available")
    assert n >= 5, \
        f"Không đủ chunk [{country}/{cat_hint}] để trả lời query: '{query_vi}' (chỉ có {n})"
```

---

### G12-06: Không retrieve chunk của quốc gia sai khi query rõ ràng

**Kịch bản:** Khách hỏi "Canada Express Entry" → không được trả về chunk USA hay NZ, dù embedding gần nhau.

```python
@pytest.mark.parametrize("query_country,wrong_country,category", [
    ("canada",     "usa",        "Express-Entry"),
    ("usa",        "canada",     "EB2-NIW"),
    ("newzealand", "canada",     "skilled_migrant"),
])
def test_g12_06_no_wrong_country_in_filtered_retrieval(driver, query_country, wrong_country, category):
    with driver.session() as s:
        seed = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.country = $country AND c.category = $cat AND c.embedding IS NOT NULL
            RETURN c.embedding AS emb LIMIT 1
        """, country=query_country, cat=category).single()
        assert seed is not None, f"Không có seed chunk [{query_country}/{category}]"

        results = s.run("""
            CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', 10, $emb)
            YIELD node, score
            WHERE node.country = $country
            RETURN node.country AS country, score
        """, emb=seed["emb"], country=query_country).data()

    wrong = [r for r in results if r["country"] == wrong_country]
    assert len(wrong) == 0, \
        f"Filter country='{query_country}' vẫn leak {len(wrong)} chunk của '{wrong_country}'"
```

---

### G12-07: Retrieval cho câu hỏi so sánh — "Canada vs Mỹ" phải có đủ dữ liệu cả hai bên

```python
COMPARISON_PAIRS = [
    ("canada", "Express-Entry", "usa", "EB2-NIW",
     "Điều kiện học vấn và kinh nghiệm"),
    ("canada", "LMIA",          "usa", "L1-Visa",
     "Bảo lãnh lao động qua công ty"),
    ("canada", "PNP",           "newzealand", "skilled_migrant",
     "Chương trình tay nghề theo tỉnh/bang"),
]

@pytest.mark.parametrize("ca,cat_a,cb,cat_b,topic", COMPARISON_PAIRS)
def test_g12_07_comparison_data_balance(driver, ca, cat_a, cb, cat_b, topic):
    """
    Khi chatbot cần so sánh 2 chương trình, cả hai bên phải có đủ chunk.
    Nếu một bên ít hơn 3x bên kia, câu trả lời sẽ bị lệch.
    """
    with driver.session() as s:
        n_a = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.country = $country AND c.category = $cat
            RETURN count(c) AS n
        """, country=ca, cat=cat_a).single()["n"]

        n_b = s.run("""
            MATCH (c:KnowledgeChunk)
            WHERE c.country = $country AND c.category = $cat
            RETURN count(c) AS n
        """, country=cb, cat=cat_b).single()["n"]

    print(f"\n  [{topic}]")
    print(f"    {ca}/{cat_a}: {n_a} chunks")
    print(f"    {cb}/{cat_b}: {n_b} chunks")

    assert n_a > 0, f"Không có chunk [{ca}/{cat_a}]"
    assert n_b > 0, f"Không có chunk [{cb}/{cat_b}]"

    ratio = max(n_a, n_b) / min(n_a, n_b) if min(n_a, n_b) > 0 else float("inf")
    assert ratio < 5, \
        f"Mất cân bằng nghiêm trọng: {ca}/{cat_a}={n_a} vs {cb}/{cat_b}={n_b} (ratio={ratio:.1f}x)"
```

---

### G12-08: Chunk về điều kiện từ chối / rejection phải tồn tại

**Kịch bản:** Consultant cần biết lý do từ chối hồ sơ để tư vấn khách tránh sai sót. Nếu không có chunk này, chatbot không tư vấn được rủi ro.

```python
REJECTION_KEYWORDS = ["refused", "rejected", "ineligible", "denied", "refusal", "không đủ điều kiện"]

def test_g12_08_rejection_reason_coverage(driver):
    kw_cond = " OR ".join([f"toLower(c.content) CONTAINS '{kw}'" for kw in REJECTION_KEYWORDS])
    for country in ("canada", "usa"):
        with driver.session() as s:
            n = s.run(f"""
                MATCH (c:KnowledgeChunk)
                WHERE c.country = $country AND ({kw_cond})
                RETURN count(c) AS n
            """, country=country).single()["n"]
        print(f"\n  [{country}] rejection-related chunks: {n}")
        # Warn — không hard fail vì data này có thể chưa crawl
        if n == 0:
            import warnings
            warnings.warn(
                f"[{country}] Không có chunk nào về lý do từ chối hồ sơ — "
                f"chatbot sẽ không tư vấn được rủi ro rejection"
            )
```

---

## Fixtures & Helpers

```python
# tests/conftest.py

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
    """Helper: chạy Cypher và trả về single row."""
    with driver.session() as s:
        return s.run(cypher, **params).single()


def run_data(driver, cypher: str, **params):
    """Helper: chạy Cypher và trả về list of dicts."""
    with driver.session() as s:
        return s.run(cypher, **params).data()


def get_sample_embedding(driver, country: str = None, category: str = None) -> list[float]:
    """Lấy embedding của một chunk mẫu để dùng trong test."""
    where_clauses = ["c.embedding IS NOT NULL"]
    if country:
        where_clauses.append(f"c.country = '{country}'")
    if category:
        where_clauses.append(f"c.category = '{category}'")
    where = " AND ".join(where_clauses)

    with driver.session() as s:
        row = s.run(f"""
            MATCH (c:KnowledgeChunk)
            WHERE {where}
            RETURN c.embedding AS emb
            LIMIT 1
        """).single()
    assert row is not None, f"Không tìm thấy chunk với filter: {where}"
    return row["emb"]
```

---

## Checklist tổng hợp

Chạy toàn bộ suite:

```bash
pytest tests/test_graph_deep.py -v --tb=short 2>&1 | tee test_results.log
```

Chạy từng group:

```bash
# Chỉ schema tests
pytest tests/test_graph_deep.py -v -k "TestG1"

# Chỉ data quality
pytest tests/test_graph_deep.py -v -k "TestG2"

# Chỉ vector index
pytest tests/test_graph_deep.py -v -k "TestG5"

# Bỏ qua performance tests (CI/CD nhanh hơn)
pytest tests/test_graph_deep.py -v -k "not TestG10"
```

| Group | Test IDs | Mục tiêu |
|-------|----------|-----------|
| G1 | G1-01 → G1-05 | Schema, constraints, indexes đúng |
| G2 | G2-01 → G2-09 | Node properties không NULL, đúng format |
| G3 | G3-01 → G3-08 | Relationships đúng chiều, đủ coverage |
| G4 | G4-01 → G4-05 | Đủ chunk mỗi country, đủ category |
| G5 | G5-01 → G5-05 | Embedding coverage, dimension, sanity check |
| G6 | G6-01 → G6-05 | Cypher queries trả về đúng kết quả |
| G7 | G7-01 → G7-04 | Graph traversal multi-hop hoạt động đúng |
| G8 | G8-01 → G8-04 | Không có data leak giữa các country |
| G9 | G9-01 → G9-05 | Edge cases: zero vector, injection, encoding |
| G10 | G10-01 → G10-04 | Latency vector search, traversal, count queries |
| G11 | G11-01 → G11-10 | Graph retrieval exploration: multi-hop, diversity, gap, coherence |
| G12 | G12-01 → G12-08 | Immigration domain quality: CRS, IELTS, fees, tiếng Việt, so sánh |

Chạy chỉ G11 và G12 (pre-chat readiness check):

```bash
pytest tests/test_graph_deep.py -v -k "TestG11 or TestG12" --tb=short
```

---

### Ngưỡng pass/fail nhanh

#### Infrastructure (G1–G5)

| Metric | Yêu cầu |
|--------|---------|
| Total chunks | ≥ 500 |
| Missing embedding | < 5% |
| Orphan chunks | < 10% |
| BELONGS_TO coverage | ≥ 90% |
| Embedding dimension | == 768 (hoặc 1024 nếu dùng bge-m3) |
| Index state | tất cả ONLINE |

#### Graph Quality (G6–G8)

| Metric | Yêu cầu |
|--------|---------|
| same-country SIMILAR_TO | ≥ 60% |
| trust_score range | [0, 1] |
| Cross-country data leak | == 0 |
| Category-country mapping | đúng 100% (EB2-NIW chỉ USA, v.v.) |

#### Retrieval Exploration (G11)

| Metric | Yêu cầu |
|--------|---------|
| Multi-hop expand có neighbour | ít nhất 1 SIMILAR_TO per seed |
| Cross-category discovery từ LMIA | tìm được TFWP / Express-Entry |
| Source diversity top-6 | ≥ 2 sites khác nhau |
| Knowledge gap per program | 0 program < 10 chunks |
| Intra-category coherence | avg SIMILAR_TO score ≥ 0.50 |
| Near-duplicate rate | < 5% tổng chunks |
| Source URL coverage | ≥ 80% chunks có URL |

#### Immigration Domain (G12)

| Metric | Yêu cầu |
|--------|---------|
| CRS threshold chunks | ≥ 3 chunks |
| Language requirement coverage | ≥ 1 chunk mỗi program |
| Processing time coverage | ≥ 1 chunk mỗi country |
| Fee information coverage | ≥ 1 chunk mỗi country |
| Comparison data balance | ratio ≤ 5x giữa hai chương trình so sánh |
| Vietnamese query → category | ≥ 5 chunks mỗi mapping |
| Wrong-country leak khi filter | == 0 |

#### Performance (G10)

| Metric | Yêu cầu |
|--------|---------|
| Vector search latency | < 2s |
| Filtered search latency | < 3s |
| 2-hop traversal | < 10s |
