# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Immigration RAG chatbot for Canada and USA immigration consulting. Combines a Neo4j Knowledge Graph with vector search to answer natural-language questions in Vietnamese and English.

**Stack:** Python 3.10+, Neo4j 5.11+ (AuraDB Free), Groq LLM (`llama-3.3-70b-versatile`), `sentence-transformers` local CPU embedding (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dim).

## Environment setup

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

Fill in `.env` (copy from `.env.example`) — must set `NEO4J_PASSWORD`. All other fields have defaults.

Start Neo4j:
```bash
docker run --name neo4j-immigration -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/yourpassword -e NEO4J_PLUGINS='["apoc"]' \
  -v $PWD/data/neo4j:/data neo4j:5.20
```

## Build pipeline (run in order)

```bash
# 1. Create Neo4j schema, constraints, and vector index
python -m graph.init_schema

# 2. Import all data (recursive handles both flat-array and single-object JSON)
python -m graph.importers.json_importer --data-dir data/data_canada --recursive
python -m graph.importers.json_importer --data-dir data/data_usa --recursive
python -m graph.importers.json_importer --data-dir data/data_newZealand --recursive

# 3. Generate and store embeddings (GPU-accelerated, batch 128)
python -m embeddings.embed_nodes --label KnowledgeChunk --batch-size 128

# 4. Build graph relationships (Category, Site, KNN SIMILAR_TO)
python -m graph.build_graph

# 5. Start API server
uvicorn api.main:app --reload --port 8000
```

Verify embeddings in Neo4j Browser:
```cypher
MATCH (c:KnowledgeChunk) WHERE c.embedding IS NULL RETURN count(c) AS missing
```

## Module structure

```
graph/
  schema.cypher              # Vector index (768-dim cosine), constraints, indexes
  init_schema.py             # Runs schema.cypher against Neo4j
  importers/
    json_importer.py         # Imports data/canada/*.json and data/mỹ/*.json
embeddings/
  hf_embedder.py             # HuggingFace Inference API wrapper (batch, retry, throttle)
  embed_nodes.py             # Fetches un-embedded nodes, calls HF API, stores vectors
retrieval/
  vector_retriever.py        # Neo4j vector index search with country/category filters
pipeline/
  entity_extractor.py        # Groq LLM → {country, category, topic} from query
  context_builder.py         # Assembles top-k chunks into a formatted prompt context
api/
  main.py                    # FastAPI app with lifespan (shared retriever + extractor)
  routes/chat.py             # POST /chat → entity extract → vector search → Groq answer
```

## Data format

Data lives under `data/data_canada/`, `data/data_usa/`, `data/data_newZealand/`. Two sub-formats coexist:

**Flat-array** (`fanpageCanada/*.json`, `fanpageluat/*.json`): each file is a JSON array of rich chunks with full `structured_data` (chunk_id, section, tags, trust_score, priority, language).

**Single-object** (all other subdirs): each `.json` file is one crawled page with fields `site`, `category`, `page_url`, `title`, `content`, `structured_data: {}`. chunk_id is MD5 of `page_url`; country inferred from directory name.

There are NO raw program/requirement/draw nodes — data is flat web chunks imported directly as `KnowledgeChunk` nodes.

## Graph schema

**Node:** `KnowledgeChunk` — properties: `chunk_id` (unique), `content`, `title`, `section`, `category`, `country`, `tags`, `source_url`, `site`, `trust_score`, `priority`, `language`, `embedding`

**Vector index:** `knowledge-chunk-embeddings` on `KnowledgeChunk.embedding` — 768-dim cosine (matches `BAAI/bge-base-en-v1.5`)

## Embedding design

`LocalEmbedder` (`embeddings/local_embedder.py`) runs `intfloat/multilingual-e5-base` via `sentence-transformers` — uses CUDA when available (RTX 3060), CPU fallback. First download ~1.1GB, cached to `~/.cache/huggingface`.
- **Documents** embed with prefix `"passage: " + title + section + content` (truncated 2000 chars)
- **Queries** embed with prefix `"query: " + text` — E5 requires these prefixes for correct retrieval
- Output is L2-normalised (`normalize_embeddings=True`)
- Vector index dimension: **768** (must match `vector.dimensions` in `schema.cypher`)
- GPU batch size: 128 (CPU: reduce to 32)

## Important constraints

- **Path quoting:** `data/mỹ/` has a Unicode directory name — always quote in shell, use `pathlib.Path` in Python
- **Import → embed order:** `json_importer` must run before `embed_nodes`
- **Embedding model swap:** changing `HF_EMBEDDING_MODEL` requires re-embedding all nodes and updating `HF_EMBEDDING_DIM` + the `vector.dimensions` in `schema.cypher`; dimension is 768 for `bge-base-en-v1.5`, 1024 for `bge-large` or `bge-m3`
- **Vietnamese queries:** `BAAI/bge-m3` handles cross-lingual retrieval significantly better than `bge-base-en` for Vietnamese input
- **Groq rate limit:** free tier ~30 req/min; each chat turn costs 2 requests (entity extract + generation)
- **embed_nodes.py is resumable:** uses `WHERE embedding IS NULL` so re-running after interruption skips already-embedded nodes
