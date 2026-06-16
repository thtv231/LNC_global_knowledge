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
    redis_client = aioredis.from_url(
        settings.redis_url, decode_responses=True, protocol=2
    )
    yield
    await redis_client.aclose()
    close_driver()


app = FastAPI(title="Immigration AI Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Intake options ────────────────────────────────────────────────────────────

def _profile_options(country: str | None, category: str | None) -> list[dict]:
    """Structured profile quick-answers shown after bot answer when we know the program."""
    if not country or not category:
        return []

    if country == "canada" and category in ("Express-Entry", "permanent_residence"):
        return [
            {"label": "🎓 Tiến sĩ / Thạc sĩ – IELTS 7.0+ – 3+ năm KN",  "value": "Profile của tôi: bằng Thạc sĩ/Tiến sĩ, IELTS 7.0 trở lên, hơn 3 năm kinh nghiệm làm việc NOC TEER 0-2"},
            {"label": "🎓 Cử nhân – IELTS 6.5 – 5+ năm KN",               "value": "Profile của tôi: bằng Cử nhân 4 năm, IELTS 6.5, hơn 5 năm kinh nghiệm làm việc thuộc NOC TEER 2-3"},
            {"label": "🎓 Cử nhân – IELTS 6.0 – 1–3 năm KN",             "value": "Profile của tôi: bằng Cử nhân, IELTS 6.0, từ 1 đến 3 năm kinh nghiệm"},
            {"label": "📋 Nhập profile cụ thể để tính điểm FSW",          "value": "Tôi muốn tính điểm FSW Point Test và CRS. Tuổi: ___, Học vấn: ___, IELTS: ___, Kinh nghiệm: ___ năm, Ngành nghề: ___"},
        ]
    if country == "canada" and category == "PNP":
        return [
            {"label": "🏙️ Muốn định cư Ontario (OINP)",          "value": "Tôi muốn tìm hiểu PNP tỉnh bang Ontario (OINP) điều kiện và stream phù hợp"},
            {"label": "🏔️ Muốn định cư British Columbia (BC PNP)", "value": "Tôi muốn tìm hiểu BC PNP British Columbia điều kiện"},
            {"label": "🌾 Muốn định cư Alberta (AINP)",            "value": "Tôi muốn tìm hiểu AINP Alberta điều kiện"},
            {"label": "📋 Tôi chưa biết tỉnh bang nào phù hợp",   "value": "Giúp tôi so sánh các tỉnh bang Canada PNP và chọn tỉnh phù hợp nhất với profile của tôi"},
        ]
    if country == "usa" and category == "EB2-NIW":
        return [
            {"label": "🔬 STEM – 10+ publications – PhD",                "value": "Profile EB-2 NIW: Tôi có bằng PhD ngành STEM, hơn 10 bài báo peer-reviewed, đang làm nghiên cứu tại Mỹ"},
            {"label": "💼 Master's – 5+ năm KN – công việc tác động Mỹ", "value": "Profile EB-2 NIW: Tôi có bằng Thạc sĩ, 5+ năm kinh nghiệm, công việc có ảnh hưởng đến lợi ích quốc gia Mỹ"},
            {"label": "🏗️ Kỹ sư / IT / Y tế – track B",                 "value": "Profile EB-2 NIW: Tôi là kỹ sư/IT/bác sĩ, chưa có nhiều publication, muốn biết cần build thêm gì trước khi nộp"},
            {"label": "📋 Nhập profile để đánh giá Track A hay B",       "value": "Đánh giá Track A hay Track B EB-2 NIW cho tôi. Ngành: ___, Học vị: ___, Số bài báo: ___, Citation: ___, Thư giới thiệu: ___"},
        ]
    if country == "usa" and category == "EB1-A":
        return [
            {"label": "🏆 Giải thưởng quốc tế + báo chí viết về tôi",     "value": "Profile EB-1A: Tôi có giải thưởng quốc tế trong ngành và được báo chí/truyền thông đề cập"},
            {"label": "📚 50+ citations – peer reviewer – hội đồng chuyên ngành", "value": "Profile EB-1A: Tôi có hơn 50 citation, làm peer reviewer cho journal quốc tế, là thành viên hội đồng chuyên ngành"},
            {"label": "💰 Lương top 10% ngành tại Mỹ",                    "value": "Profile EB-1A: Mức lương của tôi thuộc top 10% cao nhất trong ngành tại Mỹ"},
            {"label": "📋 Kiểm tra tôi đủ ≥3/10 tiêu chí EB-1A chưa",    "value": "Kiểm tra profile EB-1A của tôi đủ tiêu chí chưa: Giải thưởng: ___, Citation: ___, Báo chí: ___, Lương: ___, Thành viên hội: ___"},
        ]
    if country == "newzealand" and category == "skilled-migrant":
        return [
            {"label": "🎓 Bằng NZ/Úc + job offer NZ",                  "value": "Profile Skilled Migrant NZ: Tôi có bằng đại học tại NZ hoặc Úc và đang có job offer từ employer NZ"},
            {"label": "💼 Bằng quốc tế + 5+ năm KN ngành thiếu hụt NZ", "value": "Profile Skilled Migrant NZ: Tôi có bằng quốc tế, hơn 5 năm kinh nghiệm ngành thuộc danh sách thiếu hụt nhân lực NZ"},
            {"label": "📋 Tính điểm Skilled Migrant cho tôi",            "value": "Tính điểm Skilled Migrant Category NZ cho tôi. Tuổi: ___, Học vấn: ___, Kinh nghiệm: ___ năm, Ngành: ___, Job offer: có/không"},
        ]
    return []


def _intake_options(country: str | None, category: str | None) -> list[dict]:
    """Return quick-choice cards when the query lacks enough context."""
    if not country and not category:
        return [
            {"label": "🇨🇦 Canada",       "value": "Tôi muốn tìm hiểu về định cư Canada"},
            {"label": "🇺🇸 Mỹ (USA)",     "value": "Tôi muốn tìm hiểu về định cư Mỹ"},
            {"label": "🇳🇿 New Zealand",   "value": "Tôi muốn tìm hiểu về định cư New Zealand"},
            {"label": "So sánh cả 3 nước", "value": "So sánh định cư Canada, Mỹ và New Zealand"},
        ]
    if country == "canada" and not category:
        return [
            {"label": "Express Entry (FSW / CEC / FST)", "value": "Express Entry Canada điều kiện và quy trình"},
            {"label": "PNP – Định cư tỉnh bang",         "value": "Provincial Nominee Program Canada điều kiện"},
            {"label": "LMIA / Work Permit",               "value": "LMIA và work permit Canada"},
            {"label": "Bảo lãnh gia đình",                "value": "Bảo lãnh gia đình sang Canada điều kiện"},
        ]
    if country == "usa" and not category:
        return [
            {"label": "EB-2 NIW – Miễn yêu cầu việc làm", "value": "EB-2 NIW National Interest Waiver điều kiện và quy trình"},
            {"label": "EB-1A – Tài năng đặc biệt",         "value": "EB-1A Extraordinary Ability điều kiện"},
            {"label": "H-1B – Lao động chuyên môn",        "value": "H1B visa điều kiện và quy trình"},
            {"label": "L-1 – Chuyển nhượng nội bộ",        "value": "L1 visa chuyển nhượng nội bộ công ty"},
        ]
    if country == "newzealand" and not category:
        return [
            {"label": "Skilled Migrant Category",   "value": "Skilled Migrant Category New Zealand điều kiện"},
            {"label": "AEWV – Accredited Employer", "value": "Accredited Employer Work Visa New Zealand"},
            {"label": "Investor Visa",              "value": "Investor visa New Zealand điều kiện"},
            {"label": "Student Visa",               "value": "Student visa New Zealand"},
        ]
    return []


_GREETINGS = {"hi", "hello", "xin chào", "chào", "hey", "alo", "helo", "good morning", "good evening"}

def _is_greeting(query: str) -> bool:
    return query.strip().lower() in _GREETINGS


_CONTACT_KEYWORDS = [
    "gặp tư vấn", "gặp chuyên viên", "gặp consultant", "gặp trực tiếp",
    "liên hệ tư vấn", "muốn tư vấn riêng", "tư vấn trực tiếp",
    "gặp tư vấn viên", "muốn gặp", "để lại thông tin",
]

def _is_contact_request(query: str) -> bool:
    q = query.lower()
    return any(kw in q for kw in _CONTACT_KEYWORDS)


# ── History helpers ────────────────────────────────────────────────────────────
HISTORY_TTL = 7200  # 2 hours


async def load_history(session_id: str) -> dict:
    raw = await redis_client.get(f"chat:{session_id}")
    if not raw:
        return {"messages": [], "last_country": None, "last_category": None}
    data = json.loads(raw)
    if isinstance(data, list):          # migrate old format
        return {"messages": data, "last_country": None, "last_category": None}
    return data


async def save_history(
    session_id: str,
    messages: list[dict],
    country: str | None = None,
    category: str | None = None,
    prev: dict | None = None,
) -> None:
    data = {
        "messages":     messages,
        "last_country":  country or (prev or {}).get("last_country"),
        "last_category": category or (prev or {}).get("last_category"),
    }
    await redis_client.setex(f"chat:{session_id}", HISTORY_TTL, json.dumps(data))


# ── Request / Response models ──────────────────────────────────────────────────
class ChatRequest(BaseModel):
    query: str
    session_id: str

class IntakeSubmit(BaseModel):
    name: str
    phone: str
    profile: str
    session_id: str = ""


# ── Lead intake endpoint ───────────────────────────────────────────────────────
@app.post("/intake")
async def intake_submit(req: IntakeSubmit):
    lead = {
        "name":    req.name,
        "phone":   req.phone,
        "profile": req.profile,
        "session": req.session_id,
    }
    await redis_client.lpush("leads", json.dumps(lead, ensure_ascii=False))
    return {"status": "ok", "message": "Chuyên viên sẽ liên hệ trong 24 giờ."}


# ── SSE streaming endpoint ─────────────────────────────────────────────────────
@app.post("/chat")
@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    session = await load_history(req.session_id)
    history = session["messages"]

    initial_state = {
        "query":         req.query,
        "session_id":    req.session_id,
        "history":       history,
        "country":       session.get("last_country"),   # pre-seed so extractor uses it as fallback
        "category":      session.get("last_category"),
        "topic":         None,
        "graph_chunks":  [],
        "vector_chunks": [],
        "web_chunks":    [],
        "merged_chunks": [],
        "answer":        "",
        "sources":       [],
        "suggestions":   [],
        "stream_tokens": [],
    }

    # Which nodes emit visible status messages (in order of appearance)
    NODE_STATUS: dict[str, str] = {
        "extract_entities": "🔍 Đang phân tích câu hỏi...",
        "web_search":       "🌐 Đang tìm kiếm thông tin mới nhất từ web...",
        "vector_retrieve":  "📚 Đang tra cứu cơ sở dữ liệu...",
        "build_context":    "⚙️ Đang tổng hợp thông tin...",
        "generate":         "✍️ Đang soạn câu trả lời...",
    }

    async def event_stream():
        final_state = None
        try:
            async for event in workflow.astream_events(initial_state, version="v2"):
                kind = event.get("event")

                # Emit status when a node starts executing
                if kind == "on_chain_start":
                    node = event.get("metadata", {}).get("langgraph_node", "")
                    if node in NODE_STATUS:
                        yield f"data: {json.dumps({'type': 'status', 'step': node, 'message': NODE_STATUS[node]})}\n\n"

                elif kind == "on_chain_end":
                    node = event.get("metadata", {}).get("langgraph_node", "")
                    # Emit web results right after web_search node finishes
                    if node == "web_search":
                        web_chunks = event.get("data", {}).get("output", {}).get("web_chunks", [])
                        if web_chunks:
                            items = [
                                {"title": c["title"], "url": c["source_url"], "snippet": c["content"][:160]}
                                for c in web_chunks if c.get("title") and c.get("source_url")
                            ]
                            if items:
                                yield f"data: {json.dumps({'type': 'web_results', 'items': items})}\n\n"
                    # Capture final state when entire graph finishes
                    if event.get("name") == "LangGraph":
                        final_state = event.get("data", {}).get("output")

                elif kind == "on_chat_model_stream":
                    node = event.get("metadata", {}).get("langgraph_node", "")
                    if node != "generate":
                        continue
                    token = event.get("data", {}).get("chunk", {}).content
                    if token:
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            if final_state:
                new_history = history + [
                    {"role": "user",      "content": req.query},
                    {"role": "assistant", "content": final_state.get("answer", "")},
                ]
                country  = final_state.get("country")
                category = final_state.get("category")
                await save_history(req.session_id, new_history[-20:], country, category, session)

                is_profile  = req.query.startswith("📋 Đăng ký tư vấn chuyên sâu:")
                is_contact  = _is_contact_request(req.query) and not is_profile
                is_greeting = _is_greeting(req.query)

                # For greetings: don't inherit previous country — show country picker fresh
                if is_greeting:
                    eff_country  = None
                    eff_category = None
                else:
                    eff_country  = country or session.get("last_country")
                    eff_category = category or session.get("last_category")

                has_topic = bool(country or category)
                meta = {
                    "type":            "meta",
                    "sources":         final_state.get("sources", []) if has_topic else [],
                    "suggestions":     final_state.get("suggestions", []) if not (is_profile or is_contact) else [],
                    "country":         country,
                    "category":        category,
                    "intake_options":  [] if (is_profile or is_contact) else _intake_options(eff_country, eff_category),
                    "profile_options": _profile_options(eff_country, eff_category),
                    "consultant_ask":  is_profile or is_contact,
                    "contact_form":    is_contact,
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
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/news")
async def latest_news():
    """Fetch latest immigration news from Tavily for the welcome panel."""
    from graph.nodes.web_searcher import _COUNTRY_DOMAINS
    if not settings.tavily_api_key:
        return {"items": []}
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.search(
            query="latest immigration news Express Entry draw Canada USCIS update New Zealand 2025",
            search_depth="basic",
            max_results=6,
            include_domains=[
                "canada.ca", "moving2canada.com", "canadavisa.com",
                "uscis.gov", "travel.state.gov",
                "immigration.govt.nz",
            ],
        )
        items = [
            {
                "title":   r.get("title", ""),
                "url":     r.get("url", ""),
                "snippet": r.get("content", "")[:160],
            }
            for r in response.get("results", [])
            if r.get("title") and r.get("url")
        ]
        return {"items": items}
    except Exception:
        return {"items": []}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
