from __future__ import annotations
import os

from dotenv import load_dotenv
from fastapi import APIRouter, Request
from groq import Groq
from pydantic import BaseModel

from pipeline.context_builder import build_context

load_dotenv()

router = APIRouter()

_SYSTEM_PROMPT = """\
You are an expert immigration consultant specialising in US and Canadian immigration law.
Answer the user's question using ONLY the provided context. If the context is insufficient, say so clearly.
Always mention which program or source the information comes from.
Reply in the same language as the user's question (Vietnamese or English)."""


class ChatRequest(BaseModel):
    message: str
    country: str | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    detected: dict


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request) -> ChatResponse:
    retriever = request.app.state.retriever
    extractor = request.app.state.extractor

    entities = extractor.extract(req.message)
    country = req.country or entities.get("country")
    category = entities.get("category")

    chunks = retriever.search(req.message, country=country, category=category, top_k=6)
    context = build_context(chunks)
    sources = list({c["source_url"] for c in chunks if c.get("source_url")})

    groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
    resp = groq_client.chat.completions.create(
        model=os.environ.get("GROQ_MODEL", "llama3-70b-8192"),
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {req.message}"},
        ],
        temperature=0.3,
        max_tokens=1024,
    )

    return ChatResponse(
        answer=resp.choices[0].message.content,
        sources=sources,
        detected=entities,
    )
