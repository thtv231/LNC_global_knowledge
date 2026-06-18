# CLAUDE.md — Immigration RAG Chatbot (Full Stack)

> Instruction file cho Claude Code. Đọc toàn bộ trước khi tạo bất kỳ file nào.
> Không được tự ý thêm dependencies ngoài danh sách đã liệt kê.
> Không được tạo mock data — mọi query đều chạy thật trên Neo4j AuraDB.

---

## Tổng quan hệ thống

Chatbot tư vấn định cư Canada / Mỹ / New Zealand cho khách hàng Việt Nam.

```
Browser (React)
    │ HTTP + SSE
    ▼
NestJS Gateway  :3000   ← auth, session, rate-limit, SSE proxy
    │ HTTP stream
    ▼
Python FastAPI  :8000   ← LangGraph StateGraph, retrieval, Groq stream
    │
    ├── Neo4j AuraDB     ← KnowledgeChunk graph (đã có data + embeddings)
    ├── Redis (Upstash)  ← chat history theo session_id
    └── Groq API         ← llama-3.3-70b-versatile
```

**Nguyên tắc ưu tiên:**
1. Python service chứa toàn bộ AI logic — NestJS không gọi Groq hay Neo4j trực tiếp
2. Streaming end-to-end: Groq → FastAPI SSE → NestJS SSE proxy → React EventSource
3. Chat history lưu Redis, key = `chat:{session_id}`, TTL = 2 giờ
4. Mỗi response trả kèm `sources[]` (source_url + title + category) để hiển thị citation

---

## Cấu trúc monorepo

```
immigration-chatbot/
├── CLAUDE.md                  ← file này
├── docker-compose.yml         ← local dev: neo4j + redis
├── .env.example
│
├── apps/
│   ├── gateway/               ← NestJS (TypeScript)
│   │   ├── src/
│   │   │   ├── main.ts
│   │   │   ├── app.module.ts
│   │   │   ├── chat/
│   │   │   │   ├── chat.module.ts
│   │   │   │   ├── chat.controller.ts   ← POST /chat, GET /chat/stream/:id
│   │   │   │   ├── chat.service.ts      ← proxy sang Python, pipe SSE
│   │   │   │   └── dto/
│   │   │   │       └── chat.dto.ts
│   │   │   ├── session/
│   │   │   │   ├── session.module.ts
│   │   │   │   └── session.service.ts   ← Redis CRUD cho chat history
│   │   │   └── common/
│   │   │       ├── guards/throttle.guard.ts
│   │   │       └── interceptors/logger.interceptor.ts
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   └── ai-service/            ← Python FastAPI + LangGraph
│       ├── main.py
│       ├── requirements.txt
│       ├── graph/
│       │   ├── state.py        ← TypedDict ChatState
│       │   ├── nodes/
│       │   │   ├── entity_extractor.py
│       │   │   ├── graph_retriever.py
│       │   │   ├── vector_retriever.py
│       │   │   ├── context_builder.py
│       │   │   ├── generator.py
│       │   │   └── suggestion_generator.py
│       │   └── workflow.py     ← StateGraph assembly
│       ├── retrieval/
│       │   ├── neo4j_client.py
│       │   └── embedder.py
│       └── config.py
│
└── apps/web/                  ← React (Vite + TypeScript)
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx
    │   ├── components/
    │   │   ├── ChatWindow.tsx
    │   │   ├── MessageBubble.tsx
    │   │   ├── CitationPanel.tsx
    │   │   ├── SuggestionChips.tsx
    │   │   └── StreamingText.tsx
    │   ├── hooks/
    │   │   ├── useChat.ts       ← SSE + history state
    │   │   └── useSession.ts    ← session_id management
    │   └── types/
    │       └── chat.ts
    ├── package.json
    └── vite.config.ts
```

---

## Environment variables

**File `.env` (root) — dùng chung cho cả hai service:**

```env
# Neo4j AuraDB (đã có data)
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Groq
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_SUGGEST_MODEL=llama-3.1-8b-instant

# Redis (Upstash hoặc local)
REDIS_URL=redis://localhost:6379
# Upstash: REDIS_URL=rediss://:password@host:6380

# Python AI service
AI_SERVICE_URL=http://localhost:8000
AI_SERVICE_TIMEOUT=60000

# Embedding model (đã dùng để embed graph — KHÔNG đổi)
EMBEDDING_MODEL=intfloat/multilingual-e5-base
EMBEDDING_DIM=768

# NestJS
PORT=3000
JWT_SECRET=change_me_in_production
THROTTLE_TTL=60
THROTTLE_LIMIT=30

# React (Vite)
VITE_API_URL=http://localhost:3000
```

---

## Python AI Service (`apps/ai-service/`)

### `requirements.txt`

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
langgraph==0.1.19
langchain-groq==0.1.6
langchain-core==0.2.10
neo4j==5.20.0
sentence-transformers==3.0.1
redis==5.0.4
python-dotenv==1.0.1
pydantic==2.7.4
httpx==0.27.0
```

### `config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    groq_suggest_model: str = "llama-3.1-8b-instant"
    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_dim: int = 768
    redis_url: str = "redis://localhost:6379"

    class Config:
        env_file = "../../.env"

settings = Settings()
```

### `retrieval/embedder.py`

```python
from sentence_transformers import SentenceTransformer
from config import settings

_model: SentenceTransformer | None = None

def get_embedder() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model

def embed_query(text: str) -> list[float]:
    """E5 yêu cầu prefix 'query: ' cho câu hỏi."""
    model = get_embedder()
    vec = model.encode(f"query: {text}", normalize_embeddings=True)
    return vec.tolist()
```

### `retrieval/neo4j_client.py`

```python
from neo4j import GraphDatabase, Driver
from config import settings

_driver: Driver | None = None

def get_driver() -> Driver:
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver

def close_driver():
    global _driver
    if _driver:
        _driver.close()
        _driver = None
```

### `graph/state.py`

```python
from typing import TypedDict, Annotated
import operator

class ChatState(TypedDict):
    # Input
    query: str
    session_id: str
    history: list[dict]          # [{"role": "user"|"assistant", "content": str}]

    # Extracted entities
    country: str | None          # "canada" | "usa" | "newzealand" | None
    category: str | None         # "Express-Entry" | "EB2-NIW" | ... | None
    topic: str | None

    # Retrieved chunks
    graph_chunks: list[dict]     # từ Cypher multi-hop
    vector_chunks: list[dict]    # từ vector index
    merged_chunks: list[dict]    # sau khi merge + rank

    # Output
    answer: str
    sources: list[dict]          # [{title, source_url, category, country}]
    suggestions: list[str]       # 3 câu hỏi gợi ý tiếp theo
    stream_tokens: Annotated[list[str], operator.add]
```

### `graph/nodes/entity_extractor.py`

```python
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from config import settings
from graph.state import ChatState
import json, re

SYSTEM = """Bạn là bộ phân tích câu hỏi định cư. Trích xuất thông tin từ câu hỏi của user.

Trả về JSON hợp lệ, không markdown:
{
  "country": "canada" | "usa" | "newzealand" | null,
  "category": tên chương trình cụ thể hoặc null,
  "topic": chủ đề chính trong 5 từ
}

Các category hợp lệ:
- canada: Express-Entry, PNP, LMIA, TFWP, General
- usa: EB1-A, EB1-B, EB1-C, EB2-NIW, L1-Visa, General
- newzealand: skilled_migrant, General

Nếu không rõ country, trả null. Nếu không rõ category, trả null."""

llm = ChatGroq(
    model=settings.groq_model,
    api_key=settings.groq_api_key,
    temperature=0,
    max_tokens=200,
)

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM),
    ("human", "{query}"),
])

chain = prompt | llm

def extract_entities(state: ChatState) -> dict:
    result = chain.invoke({"query": state["query"]})
    raw = result.content.strip()
    # strip markdown code fences nếu có
    raw = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.DOTALL)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"country": None, "category": None, "topic": state["query"][:50]}
    return {
        "country": data.get("country"),
        "category": data.get("category"),
        "topic": data.get("topic", ""),
    }
```

### `graph/nodes/graph_retriever.py`

```python
from retrieval.neo4j_client import get_driver
from graph.state import ChatState

# Cypher khai thác multi-hop: vector seed → SIMILAR_TO 1-hop expand
# Sắp xếp: trust_score ưu tiên, score tổng hợp thứ hai
CYPHER_WITH_CATEGORY = """
MATCH (c:KnowledgeChunk)
WHERE c.country = $country AND c.category = $category
  AND c.embedding IS NOT NULL
WITH c LIMIT 5
OPTIONAL MATCH (c)-[r:SIMILAR_TO]->(n:KnowledgeChunk)
WHERE n.country = $country AND r.score > 0.72
WITH c,
     collect(DISTINCT {
         chunk_id: n.chunk_id,
         content:  n.content,
         title:    n.title,
         category: n.category,
         country:  n.country,
         source_url: n.source_url,
         trust_score: coalesce(n.trust_score, 0.5),
         score: r.score,
         hop: 1
     })[..3] AS neighbours
RETURN c.chunk_id    AS chunk_id,
       c.content     AS content,
       c.title       AS title,
       c.category    AS category,
       c.country     AS country,
       c.source_url  AS source_url,
       coalesce(c.trust_score, 0.5) AS trust_score,
       1.0           AS score,
       0             AS hop,
       neighbours
ORDER BY trust_score DESC
LIMIT 4
"""

CYPHER_COUNTRY_ONLY = """
MATCH (c:KnowledgeChunk)
WHERE c.country = $country AND c.embedding IS NOT NULL
WITH c ORDER BY coalesce(c.trust_score, 0.5) DESC LIMIT 3
RETURN c.chunk_id    AS chunk_id,
       c.content     AS content,
       c.title       AS title,
       c.category    AS category,
       c.country     AS country,
       c.source_url  AS source_url,
       coalesce(c.trust_score, 0.5) AS trust_score,
       1.0           AS score,
       0             AS hop,
       [] AS neighbours
"""

def graph_retrieve(state: ChatState) -> dict:
    country  = state.get("country")
    category = state.get("category")
    if not country:
        return {"graph_chunks": []}

    driver = get_driver()
    chunks = []
    with driver.session() as s:
        if category:
            rows = s.run(CYPHER_WITH_CATEGORY, country=country, category=category).data()
        else:
            rows = s.run(CYPHER_COUNTRY_ONLY, country=country).data()

        for r in rows:
            chunks.append({
                "chunk_id":   r["chunk_id"],
                "content":    r["content"],
                "title":      r["title"] or "",
                "category":   r["category"],
                "country":    r["country"],
                "source_url": r["source_url"] or "",
                "trust_score": r["trust_score"],
                "score":      r["score"],
                "hop":        r["hop"],
                "source":     "graph",
            })
            # flatten neighbours
            for nb in (r.get("neighbours") or []):
                if nb.get("chunk_id"):
                    nb["source"] = "graph_neighbour"
                    chunks.append(nb)

    return {"graph_chunks": chunks}
```

### `graph/nodes/vector_retriever.py`

```python
from retrieval.neo4j_client import get_driver
from retrieval.embedder import embed_query
from graph.state import ChatState

CYPHER_VECTOR = """
CALL db.index.vector.queryNodes('knowledge-chunk-embeddings', $top_k, $embedding)
YIELD node AS c, score
WHERE score > 0.62
  {country_filter}
RETURN c.chunk_id    AS chunk_id,
       c.content     AS content,
       c.title       AS title,
       c.category    AS category,
       c.country     AS country,
       c.source_url  AS source_url,
       coalesce(c.trust_score, 0.5) AS trust_score,
       score
ORDER BY score DESC
LIMIT $top_k
"""

def vector_retrieve(state: ChatState) -> dict:
    query   = state["query"]
    country = state.get("country")
    embedding = embed_query(query)

    country_filter = "AND c.country = $country" if country else ""
    cypher = CYPHER_VECTOR.replace("{country_filter}", country_filter)

    params: dict = {"embedding": embedding, "top_k": 6}
    if country:
        params["country"] = country

    driver = get_driver()
    chunks = []
    with driver.session() as s:
        rows = s.run(cypher, **params).data()
        for r in rows:
            chunks.append({
                "chunk_id":   r["chunk_id"],
                "content":    r["content"],
                "title":      r["title"] or "",
                "category":   r["category"],
                "country":    r["country"],
                "source_url": r["source_url"] or "",
                "trust_score": r["trust_score"],
                "score":      float(r["score"]),
                "source":     "vector",
            })
    return {"vector_chunks": chunks}
```

### `graph/nodes/context_builder.py`

```python
from graph.state import ChatState

def build_context(state: ChatState) -> dict:
    """
    Merge graph + vector chunks, dedup theo chunk_id,
    rank: trust_score * 0.4 + similarity_score * 0.6
    Giữ tối đa 6 chunks để context không quá dài.
    """
    seen: set[str] = set()
    all_chunks: list[dict] = []

    for chunk in state.get("graph_chunks", []) + state.get("vector_chunks", []):
        cid = chunk.get("chunk_id")
        if cid and cid not in seen:
            seen.add(cid)
            combined = chunk.get("trust_score", 0.5) * 0.4 + chunk.get("score", 0.5) * 0.6
            chunk["combined_score"] = combined
            all_chunks.append(chunk)

    all_chunks.sort(key=lambda x: x["combined_score"], reverse=True)
    top = all_chunks[:6]

    sources = []
    for c in top:
        if c.get("source_url"):
            sources.append({
                "title":      c["title"] or c["category"] or "",
                "source_url": c["source_url"],
                "category":   c["category"] or "",
                "country":    c["country"] or "",
            })

    return {"merged_chunks": top, "sources": sources}
```

### `graph/nodes/generator.py`

```python
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from config import settings
from graph.state import ChatState

SYSTEM = """Bạn là chuyên gia tư vấn định cư cho thị trường Việt Nam, chuyên về Canada, Mỹ, và New Zealand.

Nguyên tắc trả lời:
- Trả lời bằng ngôn ngữ của câu hỏi (tiếng Việt hoặc tiếng Anh)
- Chỉ dùng thông tin từ [CONTEXT] đã cung cấp, không bịa thêm
- Nếu context không đủ, nói thẳng: "Tôi chưa có đủ thông tin về vấn đề này"
- Trích dẫn nguồn cụ thể khi có thể (tên chương trình, tên luật)
- Không đưa ra lời khuyên pháp lý trực tiếp — khuyến nghị tham khảo luật sư hoặc consultant
- Trả lời súc tích, có cấu trúc (dùng bullet point khi liệt kê điều kiện)"""

def format_context(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        title = f"[{i}] {c['title']}" if c.get("title") else f"[{i}]"
        cat   = f"({c['category']}, {c['country']})" if c.get("category") else ""
        parts.append(f"{title} {cat}\n{c['content'][:800]}")
    return "\n\n---\n\n".join(parts)

def format_history(history: list[dict]) -> list:
    messages = []
    for h in history[-6:]:  # giữ 6 turn gần nhất
        if h["role"] == "user":
            messages.append(HumanMessage(content=h["content"]))
        else:
            messages.append(AIMessage(content=h["content"]))
    return messages

llm = ChatGroq(
    model=settings.groq_model,
    api_key=settings.groq_api_key,
    temperature=0.3,
    max_tokens=1024,
    streaming=True,
)

def generate(state: ChatState) -> dict:
    context = format_context(state.get("merged_chunks", []))
    history = format_history(state.get("history", []))

    messages = [
        SystemMessage(content=SYSTEM),
        *history,
        HumanMessage(content=f"[CONTEXT]\n{context}\n\n[CÂU HỎI]\n{state['query']}"),
    ]

    answer = ""
    tokens = []
    for chunk in llm.stream(messages):
        token = chunk.content
        if token:
            answer += token
            tokens.append(token)

    return {"answer": answer, "stream_tokens": tokens}
```

### `graph/nodes/suggestion_generator.py`

```python
from langchain_groq import ChatGroq
from config import settings
from graph.state import ChatState
import json, re

llm = ChatGroq(
    model=settings.groq_suggest_model,  # dùng model nhỏ để tiết kiệm quota
    api_key=settings.groq_api_key,
    temperature=0.5,
    max_tokens=200,
)

PROMPT = """Dựa vào câu hỏi và câu trả lời về định cư dưới đây, tạo 3 câu hỏi tiếp theo mà người dùng có thể muốn hỏi.

Câu hỏi gốc: {query}
Câu trả lời: {answer}

Trả về JSON array, không markdown:
["câu hỏi 1", "câu hỏi 2", "câu hỏi 3"]

Câu hỏi phải liên quan trực tiếp, cụ thể, bằng tiếng Việt."""

def generate_suggestions(state: ChatState) -> dict:
    try:
        result = llm.invoke(
            PROMPT.format(query=state["query"], answer=state["answer"][:400])
        )
        raw = result.content.strip()
        raw = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.DOTALL)
        suggestions = json.loads(raw)
        if isinstance(suggestions, list):
            return {"suggestions": suggestions[:3]}
    except Exception:
        pass
    return {"suggestions": []}
```

### `graph/workflow.py`

```python
from langgraph.graph import StateGraph, END
from graph.state import ChatState
from graph.nodes.entity_extractor import extract_entities
from graph.nodes.graph_retriever import graph_retrieve
from graph.nodes.vector_retriever import vector_retrieve
from graph.nodes.context_builder import build_context
from graph.nodes.generator import generate
from graph.nodes.suggestion_generator import generate_suggestions

def build_workflow() -> StateGraph:
    g = StateGraph(ChatState)

    g.add_node("extract_entities",     extract_entities)
    g.add_node("graph_retrieve",       graph_retrieve)
    g.add_node("vector_retrieve",      vector_retrieve)
    g.add_node("build_context",        build_context)
    g.add_node("generate",             generate)
    g.add_node("generate_suggestions", generate_suggestions)

    g.set_entry_point("extract_entities")
    g.add_edge("extract_entities",     "graph_retrieve")
    g.add_edge("extract_entities",     "vector_retrieve")   # parallel
    g.add_edge("graph_retrieve",       "build_context")
    g.add_edge("vector_retrieve",      "build_context")
    g.add_edge("build_context",        "generate")
    g.add_edge("generate",             "generate_suggestions")
    g.add_edge("generate_suggestions", END)

    return g.compile()

workflow = build_workflow()
```

> **Lưu ý parallel edges:** LangGraph chạy `graph_retrieve` và `vector_retrieve` song song vì cùng feed vào `build_context`. Điều này cắt latency ~40% so với sequential.

### `main.py`

```python
import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncIterator

import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import settings
from graph.workflow import workflow
from retrieval.neo4j_client import close_driver

# ── Redis ──────────────────────────────────────────────────────────────────────
redis_client: aioredis.Redis | None = None

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global redis_client
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    yield
    await redis_client.aclose()
    close_driver()

app = FastAPI(title="Immigration AI Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── History helpers ────────────────────────────────────────────────────────────
HISTORY_TTL = 7200  # 2 hours

async def load_history(session_id: str) -> list[dict]:
    raw = await redis_client.get(f"chat:{session_id}")
    return json.loads(raw) if raw else []

async def save_history(session_id: str, history: list[dict]) -> None:
    await redis_client.setex(f"chat:{session_id}", HISTORY_TTL, json.dumps(history))

# ── Request / Response models ──────────────────────────────────────────────────
class ChatRequest(BaseModel):
    query: str
    session_id: str

# ── SSE streaming endpoint ─────────────────────────────────────────────────────
@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    history = await load_history(req.session_id)

    initial_state = {
        "query":          req.query,
        "session_id":     req.session_id,
        "history":        history,
        "country":        None,
        "category":       None,
        "topic":          None,
        "graph_chunks":   [],
        "vector_chunks":  [],
        "merged_chunks":  [],
        "answer":         "",
        "sources":        [],
        "suggestions":    [],
        "stream_tokens":  [],
    }

    async def event_stream():
        final_state = None
        try:
            # LangGraph streaming: emit token events as they arrive
            async for event in workflow.astream_events(initial_state, version="v2"):
                kind = event.get("event")

                # Token streaming từ generator node
                if kind == "on_chat_model_stream":
                    token = event.get("data", {}).get("chunk", {}).content
                    if token:
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

                # Final state sau khi workflow xong
                elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                    final_state = event.get("data", {}).get("output")

            if final_state:
                # Lưu history
                new_history = history + [
                    {"role": "user",      "content": req.query},
                    {"role": "assistant", "content": final_state.get("answer", "")},
                ]
                await save_history(req.session_id, new_history[-20:])  # giữ 20 turns

                # Emit metadata event (sources + suggestions)
                meta = {
                    "type":        "meta",
                    "sources":     final_state.get("sources", []),
                    "suggestions": final_state.get("suggestions", []),
                    "country":     final_state.get("country"),
                    "category":    final_state.get("category"),
                }
                yield f"data: {json.dumps(meta)}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # tắt nginx buffering
        },
    )

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

---

## NestJS Gateway (`apps/gateway/`)

### `package.json` — dependencies cần thiết

```json
{
  "dependencies": {
    "@nestjs/common": "^10.0.0",
    "@nestjs/core": "^10.0.0",
    "@nestjs/platform-express": "^10.0.0",
    "@nestjs/throttler": "^5.0.0",
    "@nestjs/config": "^3.0.0",
    "ioredis": "^5.3.2",
    "class-validator": "^0.14.0",
    "class-transformer": "^0.5.1",
    "rxjs": "^7.8.0",
    "uuid": "^9.0.0"
  }
}
```

### `chat/dto/chat.dto.ts`

```typescript
import { IsString, IsNotEmpty, IsUUID, MaxLength } from 'class-validator';

export class ChatRequestDto {
  @IsString()
  @IsNotEmpty()
  @MaxLength(500)
  query: string;

  @IsString()
  @IsNotEmpty()
  sessionId: string;
}
```

### `session/session.service.ts`

```typescript
import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import Redis from 'ioredis';

@Injectable()
export class SessionService implements OnModuleDestroy {
  private redis: Redis;

  constructor(private config: ConfigService) {
    this.redis = new Redis(this.config.get<string>('REDIS_URL'));
  }

  async getSessionId(existingId?: string): Promise<string> {
    if (existingId) return existingId;
    const { v4: uuidv4 } = await import('uuid');
    return uuidv4();
  }

  onModuleDestroy() {
    this.redis.disconnect();
  }
}
```

### `chat/chat.service.ts`

```typescript
import { Injectable, HttpException, HttpStatus } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Observable, Subject } from 'rxjs';

export interface SseMessage {
  data: string;
}

@Injectable()
export class ChatService {
  private readonly aiServiceUrl: string;
  private readonly timeout: number;

  constructor(private config: ConfigService) {
    this.aiServiceUrl = this.config.get<string>('AI_SERVICE_URL', 'http://localhost:8000');
    this.timeout = this.config.get<number>('AI_SERVICE_TIMEOUT', 60000);
  }

  /**
   * Proxy SSE stream từ Python FastAPI về browser.
   * Dùng native fetch + ReadableStream để không buffer toàn bộ response.
   */
  streamChat(query: string, sessionId: string): Observable<SseMessage> {
    const subject = new Subject<SseMessage>();

    const run = async () => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeout);

      try {
        const res = await fetch(`${this.aiServiceUrl}/chat/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, session_id: sessionId }),
          signal: controller.signal,
        });

        if (!res.ok) {
          throw new HttpException('AI service error', HttpStatus.BAD_GATEWAY);
        }

        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const payload = line.slice(6).trim();
              if (payload === '[DONE]') {
                subject.complete();
                return;
              }
              subject.next({ data: payload });
            }
          }
        }
        subject.complete();
      } catch (err) {
        subject.error(err);
      } finally {
        clearTimeout(timer);
      }
    };

    run();
    return subject.asObservable();
  }
}
```

### `chat/chat.controller.ts`

```typescript
import {
  Controller, Post, Body, Sse, MessageEvent,
  UsePipes, ValidationPipe, Res, HttpCode,
} from '@nestjs/common';
import { Observable, map } from 'rxjs';
import { Response } from 'express';
import { ChatService } from './chat.service';
import { ChatRequestDto } from './dto/chat.dto';
import { SessionService } from '../session/session.service';
import { v4 as uuidv4 } from 'uuid';

@Controller('chat')
export class ChatController {
  constructor(
    private readonly chatService: ChatService,
    private readonly sessionService: SessionService,
  ) {}

  /**
   * POST /chat
   * Body: { query: string, sessionId?: string }
   * Returns SSE stream với Content-Type: text/event-stream
   */
  @Post()
  @HttpCode(200)
  @UsePipes(new ValidationPipe({ whitelist: true }))
  streamChat(
    @Body() dto: ChatRequestDto,
    @Res() res: Response,
  ): void {
    const sessionId = dto.sessionId || uuidv4();

    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Session-Id', sessionId);
    res.flushHeaders();

    const stream$ = this.chatService.streamChat(dto.query, sessionId);

    stream$.subscribe({
      next: (msg) => {
        res.write(`data: ${msg.data}\n\n`);
      },
      error: (err) => {
        res.write(`data: ${JSON.stringify({ type: 'error', message: err.message })}\n\n`);
        res.end();
      },
      complete: () => {
        res.write('data: [DONE]\n\n');
        res.end();
      },
    });

    // Cleanup khi client disconnect
    res.on('close', () => stream$.subscribe().unsubscribe());
  }
}
```

### `app.module.ts`

```typescript
import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ThrottlerModule, ThrottlerGuard } from '@nestjs/throttler';
import { APP_GUARD } from '@nestjs/core';
import { ChatModule } from './chat/chat.module';
import { SessionModule } from './session/session.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true, envFilePath: '../../.env' }),
    ThrottlerModule.forRoot([{ ttl: 60000, limit: 30 }]),  // 30 req/min (Groq free tier)
    ChatModule,
    SessionModule,
  ],
  providers: [{ provide: APP_GUARD, useClass: ThrottlerGuard }],
})
export class AppModule {}
```

---

## React Frontend (`apps/web/`)

### `types/chat.ts`

```typescript
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  suggestions?: string[];
  isStreaming?: boolean;
}

export interface Source {
  title: string;
  source_url: string;
  category: string;
  country: string;
}

export interface ChatMeta {
  sources: Source[];
  suggestions: string[];
  country: string | null;
  category: string | null;
}
```

### `hooks/useSession.ts`

```typescript
import { useState, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';

export function useSession(): string {
  const [sessionId] = useState<string>(() => {
    // sessionStorage scope: mỗi tab là một session riêng
    const existing = sessionStorage.getItem('chat_session_id');
    if (existing) return existing;
    const newId = uuidv4();
    sessionStorage.setItem('chat_session_id', newId);
    return newId;
  });
  return sessionId;
}
```

### `hooks/useChat.ts`

```typescript
import { useState, useCallback, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { Message, ChatMeta } from '../types/chat';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:3000';

export function useChat(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const abortRef = useRef<(() => void) | null>(null);

  const sendMessage = useCallback(async (query: string) => {
    if (!query.trim() || isLoading) return;

    // Thêm user message
    const userMsg: Message = { id: uuidv4(), role: 'user', content: query };
    const assistantId = uuidv4();
    const assistantMsg: Message = {
      id: assistantId, role: 'assistant', content: '', isStreaming: true,
    };
    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setIsLoading(true);

    let cancelled = false;
    abortRef.current = () => { cancelled = true; };

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, sessionId }),
      });

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done || cancelled) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (raw === '[DONE]') break;

          try {
            const event = JSON.parse(raw);

            if (event.type === 'token') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: m.content + event.content }
                  : m
              ));
            } else if (event.type === 'meta') {
              const meta = event as ChatMeta;
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, sources: meta.sources, suggestions: meta.suggestions, isStreaming: false }
                  : m
              ));
            } else if (event.type === 'error') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: `Có lỗi xảy ra: ${event.message}`, isStreaming: false }
                  : m
              ));
            }
          } catch {
            // JSON parse error — bỏ qua dòng này
          }
        }
      }
    } catch (err) {
      if (!cancelled) {
        setMessages(prev => prev.map(m =>
          m.id === assistantId
            ? { ...m, content: 'Không thể kết nối đến server. Vui lòng thử lại.', isStreaming: false }
            : m
        ));
      }
    } finally {
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, isStreaming: false } : m
      ));
      setIsLoading(false);
    }
  }, [sessionId, isLoading]);

  const cancelStream = useCallback(() => {
    abortRef.current?.();
  }, []);

  return { messages, isLoading, sendMessage, cancelStream };
}
```

### `components/StreamingText.tsx`

```tsx
import { useEffect, useState } from 'react';

interface Props {
  content: string;
  isStreaming: boolean;
}

export function StreamingText({ content, isStreaming }: Props) {
  return (
    <div className="whitespace-pre-wrap leading-relaxed">
      {content}
      {isStreaming && (
        <span className="inline-block w-2 h-4 ml-0.5 bg-current animate-pulse rounded-sm" />
      )}
    </div>
  );
}
```

### `components/CitationPanel.tsx`

```tsx
import { Source } from '../types/chat';

interface Props {
  sources: Source[];
}

const COUNTRY_LABEL: Record<string, string> = {
  canada: '🇨🇦 Canada',
  usa: '🇺🇸 Mỹ',
  newzealand: '🇳🇿 New Zealand',
};

export function CitationPanel({ sources }: Props) {
  if (!sources?.length) return null;

  return (
    <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
      <p className="text-xs text-gray-500 mb-1.5">Nguồn tham khảo</p>
      <div className="flex flex-col gap-1">
        {sources.map((s, i) => (
          <a
            key={i}
            href={s.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-400 hover:underline truncate"
          >
            <span className="shrink-0">{COUNTRY_LABEL[s.country] ?? s.country}</span>
            <span className="truncate">{s.title || s.category}</span>
          </a>
        ))}
      </div>
    </div>
  );
}
```

### `components/SuggestionChips.tsx`

```tsx
interface Props {
  suggestions: string[];
  onSelect: (q: string) => void;
  disabled: boolean;
}

export function SuggestionChips({ suggestions, onSelect, disabled }: Props) {
  if (!suggestions?.length) return null;

  return (
    <div className="flex flex-wrap gap-2 mt-3">
      {suggestions.map((s, i) => (
        <button
          key={i}
          onClick={() => !disabled && onSelect(s)}
          disabled={disabled}
          className="text-xs px-3 py-1.5 rounded-full border border-gray-200 dark:border-gray-600
                     text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700
                     disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {s}
        </button>
      ))}
    </div>
  );
}
```

### `components/MessageBubble.tsx`

```tsx
import { Message } from '../types/chat';
import { StreamingText } from './StreamingText';
import { CitationPanel } from './CitationPanel';
import { SuggestionChips } from './SuggestionChips';

interface Props {
  message: Message;
  isLoading: boolean;
  onSuggestionSelect: (q: string) => void;
}

export function MessageBubble({ message, isLoading, onSuggestionSelect }: Props) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`max-w-[80%] ${isUser
        ? 'bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5'
        : 'bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-2xl rounded-tl-sm px-4 py-3'
      }`}>
        <StreamingText content={message.content} isStreaming={message.isStreaming ?? false} />
        {!isUser && (
          <>
            <CitationPanel sources={message.sources ?? []} />
            <SuggestionChips
              suggestions={message.suggestions ?? []}
              onSelect={onSuggestionSelect}
              disabled={isLoading}
            />
          </>
        )}
      </div>
    </div>
  );
}
```

### `components/ChatWindow.tsx`

```tsx
import { useState, useRef, useEffect } from 'react';
import { MessageBubble } from './MessageBubble';
import { useChat } from '../hooks/useChat';
import { useSession } from '../hooks/useSession';

const INITIAL_SUGGESTIONS = [
  'Điều kiện Express Entry Canada năm 2024?',
  'So sánh EB2-NIW và EB1-A Mỹ',
  'Chương trình Skilled Migrant New Zealand',
];

export function ChatWindow() {
  const sessionId = useSession();
  const { messages, isLoading, sendMessage } = useChat(sessionId);
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const q = input.trim();
    if (!q) return;
    setInput('');
    await sendMessage(q);
  };

  return (
    <div className="flex flex-col h-screen max-w-3xl mx-auto">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <h1 className="text-base font-semibold text-gray-900 dark:text-white">
          Tư vấn định cư 🌏
        </h1>
        <p className="text-xs text-gray-500">Canada · Mỹ · New Zealand</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-4">
            <p className="text-gray-400 text-sm">Tôi có thể giúp gì cho bạn?</p>
            <div className="flex flex-wrap justify-center gap-2">
              {INITIAL_SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(s)}
                  className="text-sm px-4 py-2 rounded-full border border-gray-200 dark:border-gray-600
                             text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <MessageBubble
            key={msg.id}
            message={msg}
            isLoading={isLoading}
            onSuggestionSelect={sendMessage}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700">
        <div className="flex gap-2">
          <input
            className="flex-1 rounded-xl border border-gray-200 dark:border-gray-600
                       bg-white dark:bg-gray-800 text-gray-900 dark:text-white
                       px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Hỏi về định cư Canada, Mỹ, New Zealand..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="px-4 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-medium
                       hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? '...' : 'Gửi'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

---

## Docker Compose (local dev)

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru

  # Neo4j chỉ cần cho local dev — production dùng AuraDB
  neo4j:
    image: neo4j:5.20
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/yourpassword
      - NEO4J_PLUGINS=["apoc"]
    volumes:
      - neo4j_data:/data

volumes:
  neo4j_data:
```

---

## Thứ tự build (Claude Code thực hiện theo thứ tự này)

```
Phase 1 — Python AI Service
  1. apps/ai-service/config.py
  2. apps/ai-service/retrieval/embedder.py
  3. apps/ai-service/retrieval/neo4j_client.py
  4. apps/ai-service/graph/state.py
  5. apps/ai-service/graph/nodes/entity_extractor.py
  6. apps/ai-service/graph/nodes/graph_retriever.py
  7. apps/ai-service/graph/nodes/vector_retriever.py
  8. apps/ai-service/graph/nodes/context_builder.py
  9. apps/ai-service/graph/nodes/generator.py
  10. apps/ai-service/graph/nodes/suggestion_generator.py
  11. apps/ai-service/graph/workflow.py
  12. apps/ai-service/main.py
  → Test: curl -N -X POST localhost:8000/chat/stream -H "Content-Type: application/json"
           -d '{"query":"Express Entry cần bao nhiêu điểm CRS?","session_id":"test-1"}'

Phase 2 — NestJS Gateway
  13. apps/gateway/ scaffold với nest new
  14. apps/gateway/src/chat/dto/chat.dto.ts
  15. apps/gateway/src/session/session.service.ts
  16. apps/gateway/src/chat/chat.service.ts
  17. apps/gateway/src/chat/chat.controller.ts
  18. apps/gateway/src/app.module.ts
  → Test: curl -N -X POST localhost:3000/chat
           -H "Content-Type: application/json"
           -d '{"query":"LMIA là gì?","sessionId":""}'

Phase 3 — React Frontend
  19. apps/web/ scaffold với vite
  20. apps/web/src/types/chat.ts
  21. apps/web/src/hooks/useSession.ts
  22. apps/web/src/hooks/useChat.ts
  23. apps/web/src/components/StreamingText.tsx
  24. apps/web/src/components/CitationPanel.tsx
  25. apps/web/src/components/SuggestionChips.tsx
  26. apps/web/src/components/MessageBubble.tsx
  27. apps/web/src/components/ChatWindow.tsx
  28. apps/web/src/App.tsx
```

---

## Gotchas quan trọng — Claude Code phải nhớ

**Neo4j:**
- Vector index name: `knowledge-chunk-embeddings` (không đổi)
- Embedding prefix bắt buộc: `"query: " + text` cho E5 model
- Dimension: 768 — nếu khác sẽ lỗi silently (trả về wrong results)
- `OPTIONAL MATCH` trong Cypher — không dùng `MATCH` cho expand, tránh null khi không có SIMILAR_TO

**LangGraph:**
- `astream_events(version="v2")` — bắt buộc version="v2" để nhận `on_chat_model_stream`
- `stream_tokens` dùng `Annotated[list[str], operator.add]` — LangGraph concat thay vì overwrite
- Parallel edges (`graph_retrieve` + `vector_retrieve`): cả hai node phải return dict đúng key trong state

**SSE streaming:**
- NestJS: dùng `res.flushHeaders()` ngay sau `setHeader` — không có cái này browser không nhận stream
- Header `X-Accel-Buffering: no` bắt buộc nếu deploy sau nginx/Render
- React: đọc `res.body.getReader()` trực tiếp — không dùng `EventSource` API vì cần POST body

**Groq rate limit:**
- Free tier: 30 req/min — ThrottlerGuard ở NestJS giới hạn đúng 30/min
- `suggestion_generator` dùng `llama-3.1-8b-instant` (nhanh hơn, rẻ hơn) thay vì 70b
- Mỗi turn tốn 2 calls (entity extract + generate) + 1 call suggest = 3 total

**Deploy (Render):**
- Python service: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- NestJS: `node dist/main.js` sau `npm run build`
- Set env var `AI_SERVICE_URL` trỏ đến Render URL của Python service
- Redis: Upstash free tier, set `REDIS_URL=rediss://...` (TLS)

---

## Checklist trước khi ship

```
[ ] Python service: curl /health trả về 200
[ ] Streaming: token xuất hiện từng chữ, không bị batch
[ ] History: turn 2 có context từ turn 1
[ ] Sources: CitationPanel hiển thị URL thật, click được
[ ] Suggestions: 3 chip hiện sau mỗi answer, click tự fill input
[ ] Rate limit: 31st request trong 1 phút trả về 429
[ ] Empty state: 3 suggestion chips hiện khi chưa có message
[ ] Mobile: layout không vỡ ở màn hình 375px
[ ] Dark mode: tất cả text readable (dùng Tailwind dark: prefix)
```
