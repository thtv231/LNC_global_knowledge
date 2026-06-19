from __future__ import annotations
import asyncio
import json
import os
import logging

import random
from dotenv import load_dotenv
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

from pipeline.context_builder import build_context

load_dotenv()
logger = logging.getLogger(__name__)

router = APIRouter()


def _pick_deepseek_key() -> str:
    keys_str = os.environ.get("DEEPSEEK_API_KEYS", "")
    keys = [k.strip() for k in keys_str.split(",") if k.strip()]
    if not keys:
        keys = [os.environ["DEEPSEEK_API_KEY"]]
    return random.choice(keys)


def _get_deepseek() -> OpenAI:
    return OpenAI(
        api_key=_pick_deepseek_key(),
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )


_SYSTEM_PROMPT = """\
Bạn là chuyên viên tư vấn định cư cao cấp của L&C Global, chuyên về luật định cư Canada, Mỹ và New Zealand.
Trả lời câu hỏi của người dùng CHỈ dựa trên context được cung cấp. Nếu context không đủ, nói rõ ràng.
Luôn đề cập nguồn thông tin và chương trình liên quan.
Trả lời bằng ngôn ngữ của người dùng (Tiếng Việt hoặc Tiếng Anh).
Câu trả lời rõ ràng, thực tế, có cấu trúc."""

_SUGGESTIONS_BY_TOPIC = {
    "eb1a": [
        "EB-1A cần bao nhiêu bài báo quốc tế để đủ tiêu chí?",
        "Thư giới thiệu cho EB-1A nên xin từ ai?",
        "RFE EB-1A hay gặp vấn đề gì nhất?",
    ],
    "niw": [
        "EB-2 NIW 3 Prong cần chứng minh những gì?",
        "Bác sĩ lâm sàng có lợi thế gì khi nộp NIW?",
        "Mất bao lâu để NIW được duyệt?",
    ],
    "canada": [
        "Điểm CRS tối thiểu cho Express Entry là bao nhiêu?",
        "PNP tỉnh nào dễ được mời nhất hiện tại?",
        "LMIA khác gì so với Express Entry?",
    ],
    "newzealand": [
        "Điểm Skilled Migrant NZ tính như thế nào?",
        "AEWV cần employer accreditation không?",
        "Thời gian xử lý visa NZ hiện tại là bao lâu?",
    ],
}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _pick_suggestions(entities: dict) -> list[str]:
    country = (entities.get("country") or "").lower()
    category = (entities.get("category") or "").lower()
    if "eb1" in category:
        return _SUGGESTIONS_BY_TOPIC["eb1a"]
    if "niw" in category or "eb2" in category:
        return _SUGGESTIONS_BY_TOPIC["niw"]
    if country == "canada":
        return _SUGGESTIONS_BY_TOPIC["canada"]
    if country == "newzealand":
        return _SUGGESTIONS_BY_TOPIC["newzealand"]
    return _SUGGESTIONS_BY_TOPIC["canada"]


class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None
    country: str | None = None


async def _stream_chat(req: ChatRequest, request: Request):
    retriever = request.app.state.retriever
    extractor = request.app.state.extractor

    try:
        # Step 1 — entity extraction (sync → thread)
        yield _sse({"type": "status", "message": "Đang phân tích câu hỏi..."})
        entities = await asyncio.to_thread(extractor.extract, req.query)
        country = req.country or entities.get("country")
        category = entities.get("category")

        # Step 2 — vector search (sync → thread)
        yield _sse({"type": "status", "message": "Đang tìm kiếm tài liệu liên quan..."})
        chunks = await asyncio.to_thread(
            retriever.search, req.query,
            country, category, 6
        )
        context = build_context(chunks)

        sources = []
        for c in chunks:
            if c.get("source_url"):
                sources.append({
                    "title": c.get("title", ""),
                    "source_url": c.get("source_url", ""),
                    "category": c.get("category", ""),
                    "country": c.get("country", ""),
                    "is_web": False,
                })

        # Step 3 — stream DeepSeek response (true token-by-token via queue bridge)
        yield _sse({"type": "status", "message": "Đang tổng hợp câu trả lời..."})
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nCâu hỏi: {req.query}"},
        ]

        token_queue: asyncio.Queue[str | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _stream_to_queue():
            try:
                stream = _get_deepseek().chat.completions.create(
                    model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
                    messages=messages,
                    temperature=0.3,
                    max_tokens=1024,
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        loop.call_soon_threadsafe(token_queue.put_nowait, delta)
            except Exception as e:
                logger.exception("DeepSeek stream error")
                loop.call_soon_threadsafe(token_queue.put_nowait, f"\n\n[Lỗi: {e}]")
            finally:
                loop.call_soon_threadsafe(token_queue.put_nowait, None)

        loop.run_in_executor(None, _stream_to_queue)

        while True:
            token = await token_queue.get()
            if token is None:
                break
            yield _sse({"type": "token", "content": token})

        # Step 4 — meta (sources, suggestions)
        suggestions = _pick_suggestions(entities)
        yield _sse({
            "type": "meta",
            "sources": sources,
            "suggestions": suggestions,
            "country": country,
            "category": category,
            "intake_options": [],
            "profile_options": [],
            "consultant_ask": len(chunks) > 0,
            "contact_form": False,
        })
        yield "data: [DONE]\n\n"

    except Exception as exc:
        logger.exception("Stream chat error")
        yield _sse({"type": "error", "message": str(exc)})


@router.post("/chat/stream")
async def stream_chat(req: ChatRequest, request: Request):
    return StreamingResponse(
        _stream_chat(req, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# Legacy non-streaming endpoint kept for compatibility
class LegacyChatRequest(BaseModel):
    message: str
    country: str | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    detected: dict


@router.post("/chat", response_model=ChatResponse)
def chat(req: LegacyChatRequest, request: Request) -> ChatResponse:
    retriever = request.app.state.retriever
    extractor = request.app.state.extractor
    entities = extractor.extract(req.message)
    country = req.country or entities.get("country")
    category = entities.get("category")
    chunks = retriever.search(req.message, country=country, category=category, top_k=6)
    context = build_context(chunks)
    sources = list({c["source_url"] for c in chunks if c.get("source_url")})
    resp = _get_deepseek().chat.completions.create(
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {req.message}"},
        ],
        temperature=0.3,
        max_tokens=1024,
    )
    return ChatResponse(answer=resp.choices[0].message.content, sources=sources, detected=entities)
