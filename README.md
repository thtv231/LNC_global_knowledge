# Immigration RAG Chatbot — Neo4j + Groq + HuggingFace

Chatbot tư vấn định cư Canada và Mỹ, kết hợp Knowledge Graph (Neo4j) và RAG. Hệ thống xử lý cả dữ liệu structured (JSON programs) và unstructured (PDF sách luật), trả lời câu hỏi bằng ngôn ngữ tự nhiên và đánh giá hồ sơ khách hàng.

---

## Kiến trúc tổng quan

```
User query
    │
    ▼
Entity Extraction (Groq LLM)
    │  → country, program type, NOC, province...
    │
    ├─► Neo4j Graph Traversal          ← JSON data đã import
    │       Programs, Requirements,
    │       Draw history, Eligibility
    │
    ├─► Vector Search (Neo4j)          ← PDF đã chunk + embed
    │       HuggingFace embedding
    │       Policy text, Case law
    │
    └─► Context Assembly
            │
            ▼
        Groq LLM (llama3 / mixtral)
            │
            ▼
        Response + Gap Analysis
```

---

## Cấu trúc dữ liệu

```
data/
├── book/
│   ├── can/
│   │   └── SOR-2002-227.pdf              # Immigration and Refugee Protection Regulations
│   └── usa/
│       ├── case/                          # Case law PDFs
│       ├── manual/                        # USCIS policy manual PDFs
│       ├── 6244467-Fundamentals-of-Immigration-Law-pdf.pdf
│       ├── COMPS-1376.pdf
│       ├── Immigration_Law_An_Open_Casebook_2.1.pdf
│       ├── Immigration_Law_An_Open_Casebook_3.0.pdf
│       └── Immigration_Law_Statutory_Supplement_2025.pdf
├── canada/
│   ├── Express-Entry.json
│   ├── General.json
│   ├── LMIA.json
│   ├── PNP.json
│   └── TFWP.json
└── mỹ/
    ├── EB1.json
    ├── EB1-A.json
    ├── EB1-B.json
    ├── EB1-C.json
    ├── EB2-NIW.json
    ├── General.json
    ├── L1-Visa.json
    └── NIW-Entrepreneurs.json
```

### Hai loại data — hai pipeline khác nhau

| Loại | Source | Pipeline | Lưu vào Neo4j |
|---|---|---|---|
| Structured | `canada/*.json`, `mỹ/*.json` | Parse → tạo nodes/relationships | Nodes có properties đầy đủ |
| Unstructured | `book/**/*.pdf` | Chunk → embed → index | Node `PolicyChunk` với embedding |

---

## Cấu trúc project

```
immigration-rag/
├── data/                          # Raw data (xem trên)
├── graph/
│   ├── schema.cypher              # Constraints, indexes, vector index
│   ├── importers/
│   │   ├── canada_importer.py     # Import canada/*.json → Neo4j nodes
│   │   ├── usa_importer.py        # Import mỹ/*.json → Neo4j nodes
│   │   └── pdf_chunker.py         # Chunk PDF → PolicyChunk nodes
│   └── queries/
│       ├── eligibility.cypher
│       ├── gap_analysis.cypher
│       └── rag_context.cypher
├── embeddings/
│   ├── hf_embedder.py             # HuggingFace embedding wrapper
│   └── embed_nodes.py             # Batch embed và store vào Neo4j
├── retrieval/
│   ├── graph_retriever.py
│   ├── vector_retriever.py
│   └── hybrid_retriever.py
├── pipeline/
│   ├── entity_extractor.py        # Groq LLM extract entities
│   ├── context_builder.py
│   └── evaluator.py
├── api/
│   ├── main.py
│   └── routes/
│       ├── chat.py
│       └── profile.py
├── .env                           # API keys (không commit)
├── .env.example
├── requirements.txt
└── docker-compose.yml
```

---

## Graph schema

### Node labels

| Label | Source data | Properties chính |
|---|---|---|
| `Program` | `canada/*.json`, `mỹ/*.json` | `id, name, type, country, active` |
| `Province` | `canada/PNP.json` | `code, name, country` |
| `Requirement` | Tất cả JSON | `type, min_clb, min_years, noc_teer` |
| `Occupation` | JSON + NOC mapping | `noc_code, title, teer, soc_code` |
| `Draw` | `canada/Express-Entry.json` | `date, min_crs, invited` |
| `PolicyChunk` | `book/**/*.pdf` | `text, source_file, page, embedding` |
| `Applicant` | Runtime (API) | `id, age, education, ielts_*, exp_years` |

### Relationship types

```
(Province)-[:ADMINISTERS]->(Program)
(Program)-[:REQUIRES]->(Requirement)
(Program)-[:TARGETS]->(Occupation)
(Draw)-[:BELONGS_TO]->(Program)
(PolicyChunk)-[:REFERENCES]->(Program)
(PolicyChunk)-[:SOURCE_FROM]->(Country)
(Applicant)-[:APPLIED_TO {outcome, date}]->(Program)
(Requirement)-[:CONDITIONAL_ON]->(Requirement)
```

### Vector index

```cypher
CREATE VECTOR INDEX policy-chunk-embeddings
FOR (c:PolicyChunk) ON (c.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 768,
  `vector.similarity_function`: 'cosine'
}}

CREATE VECTOR INDEX program-embeddings
FOR (p:Program) ON (p.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 768,
  `vector.similarity_function`: 'cosine'
}}
```

> Dimension = 768 cho `BAAI/bge-base-en-v1.5`. Đổi thành 1024 nếu dùng `bge-m3`.

---

## Cài đặt

### Yêu cầu

- Python 3.10+
- Neo4j 5.11+ (Docker hoặc AuraDB Free)
- GROQ_API_KEY và HuggingFace model (local hoặc HF Inference API)

### 1. Clone và cài dependencies

```bash
git clone https://github.com/your-org/immigration-rag.git
cd immigration-rag
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Cấu hình `.env`

File `.env` đã có sẵn — điền các giá trị còn thiếu:

```env
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=yourpassword

# Groq
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama3-70b-8192          # hoặc mixtral-8x7b-32768

# HuggingFace Embedding
HF_EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
HF_EMBEDDING_DIM=768
# Nếu dùng HF Inference API thay vì local:
# HF_API_TOKEN=hf_...

# App
API_PORT=8000
```

### 3. Chạy Neo4j

```bash
docker run \
  --name neo4j-immigration \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/yourpassword \
  -e NEO4J_PLUGINS='["apoc"]' \
  -v $PWD/data/neo4j:/data \
  neo4j:5.20
```

### 4. Khởi tạo schema

```bash
python -m graph.init_schema
```

---

## Import data

Chạy theo thứ tự — JSON trước, PDF sau.

### Bước 1 — Import JSON (Canada)

```bash
python -m graph.importers.canada_importer \
  --data-dir data/canada \
  --programs Express-Entry.json PNP.json LMIA.json TFWP.json General.json
```

Tạo các nodes: `Program`, `Province`, `Requirement`, `Occupation`, `Draw`.

### Bước 2 — Import JSON (USA)

```bash
python -m graph.importers.usa_importer \
  --data-dir "data/mỹ" \
  --programs EB1.json EB1-A.json EB1-B.json EB1-C.json \
             EB2-NIW.json L1-Visa.json NIW-Entrepreneurs.json General.json
```

### Bước 3 — Chunk và index PDF

```bash
# Canada legal docs
python -m graph.importers.pdf_chunker \
  --source data/book/can \
  --country canada \
  --chunk-size 512 \
  --chunk-overlap 64

# USA legal docs + case law
python -m graph.importers.pdf_chunker \
  --source data/book/usa \
  --country usa \
  --chunk-size 512 \
  --chunk-overlap 64
```

Mỗi chunk tạo một `PolicyChunk` node với `text`, `source_file`, `page`, `country`.

### Bước 4 — Generate embeddings

```bash
# Embed PolicyChunk nodes (PDF chunks)
python -m embeddings.embed_nodes \
  --label PolicyChunk \
  --text-property text \
  --batch-size 32

# Embed Program nodes
python -m embeddings.embed_nodes \
  --label Program \
  --text-property description \
  --batch-size 64
```

Kiểm tra sau khi embed:

```cypher
// Xác nhận đã embed đủ
MATCH (c:PolicyChunk) WHERE c.embedding IS NULL RETURN count(c) AS missing
MATCH (p:Program) WHERE p.embedding IS NULL RETURN count(p) AS missing
```

---

## Chạy API server

```bash
uvicorn api.main:app --reload --port 8000
```

### Chat

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tôi muốn bảo lãnh người thân qua Canada diện PNP",
    "country": "canada",
    "session_id": "abc123"
  }'
```

### Đánh giá hồ sơ

```bash
curl -X POST http://localhost:8000/profile/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "country": "canada",
    "age": 32,
    "education": "bachelor",
    "ielts_reading": 7.0,
    "ielts_writing": 6.5,
    "ielts_speaking": 7.0,
    "ielts_listening": 7.5,
    "exp_years": 5,
    "noc_code": "21232"
  }'
```

---

## Retrieval pipeline

```python
# entity_extractor.py — dùng Groq
entities = groq_client.extract(query)
# → {country: "canada", program_type: "pnp", province: "ON"}

# graph_retriever.py — Cypher traversal
graph_ctx = graph_retriever.query(entities)
# → programs eligible, requirements, draw history

# vector_retriever.py — hybrid search trong Neo4j
vector_ctx = vector_retriever.search(
    query_text=query,
    country=entities["country"],   # filter theo Canada / USA
    top_k=5
)

# context_builder.py — assemble prompt
context = f"""
[PROGRAMS]
{graph_ctx}

[POLICY REFERENCE]
{vector_ctx}
"""

# Groq generation
response = groq_client.chat.completions.create(
    model=os.getenv("GROQ_MODEL"),
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
    ]
)
```

### Hybrid Cypher query

```cypher
// Vector search kết hợp filter country
CALL db.index.vector.queryNodes('policy-chunk-embeddings', 8, $queryVector)
YIELD node AS chunk, score
WHERE score > 0.70
  AND chunk.country = $country
OPTIONAL MATCH (chunk)-[:REFERENCES]->(p:Program)
RETURN chunk.text AS text,
       chunk.source_file AS source,
       chunk.page AS page,
       score,
       collect(p.name) AS related_programs
ORDER BY score DESC
```

---

## Embedding model

Mặc định dùng `BAAI/bge-base-en-v1.5` (local, không cần API key):

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer(os.getenv("HF_EMBEDDING_MODEL"))
embeddings = model.encode(texts, normalize_embeddings=True)
```

Nếu muốn dùng model mạnh hơn:

| Model | Dim | Ghi chú |
|---|---|---|
| `BAAI/bge-base-en-v1.5` | 768 | Mặc định, nhẹ, nhanh |
| `BAAI/bge-large-en-v1.5` | 1024 | Tốt hơn, nặng hơn |
| `BAAI/bge-m3` | 1024 | Multilingual, tốt nhất cho tiếng Việt |

> Khi đổi model phải re-embed toàn bộ và update `HF_EMBEDDING_DIM` trong `.env` và trong Cypher tạo vector index.

---

## Lưu ý

**PDF chunking**
Sách luật (`Immigration_Law_An_Open_Casebook`) có cấu trúc chương/section — nên dùng semantic chunking theo heading thay vì fixed-size. File `case/` và `manual/` chunk fixed-size là đủ.

**Groq rate limit**
Free tier Groq giới hạn ~30 req/min. Với entity extraction + generation mỗi turn tốn 2 request — cân nhắc cache entity extraction theo session.

**Tiếng Việt**
Query từ khách hàng thường tiếng Việt. Embed query bằng cùng model với document (BGE-M3 handle tốt hơn bge-base cho cross-lingual retrieval).

**Data thư mục `mỹ/`**
Tên thư mục có dấu — đảm bảo đường dẫn được quote đúng trong shell và Python `pathlib.Path`.
