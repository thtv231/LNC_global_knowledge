"""Facebook Messenger webhook — verify + receive + reply."""
from __future__ import annotations
import asyncio
import hashlib
import hmac
import logging
import os

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from pipeline.context_builder import build_context

load_dotenv()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook/facebook", tags=["messenger"])

MESSENGER_API = "https://graph.facebook.com/v19.0/me/messages"

_SYSTEM_PROMPT = """\
Bạn là chuyên viên tư vấn định cư cao cấp của L&C Global, chuyên về luật định cư Canada, Mỹ và New Zealand.
Trả lời câu hỏi của người dùng CHỈ dựa trên context được cung cấp. Nếu context không đủ, nói rõ ràng.
Luôn đề cập nguồn thông tin và chương trình liên quan.
Trả lời bằng ngôn ngữ của người dùng (Tiếng Việt hoặc Tiếng Anh).
Câu trả lời ngắn gọn, rõ ràng, có cấu trúc. Không dài quá 1000 ký tự vì giao diện Messenger."""


# ── helpers ──────────────────────────────────────────────────────────────────

def _page_token() -> str:
    t = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    if not t:
        raise RuntimeError("FB_PAGE_ACCESS_TOKEN not set")
    return t


def _verify_signature(body: bytes, sig_header: str | None) -> bool:
    """Validate X-Hub-Signature-256 from Facebook."""
    secret = os.environ.get("FB_APP_SECRET", "")
    if not secret:
        return True  # skip verification when secret not configured
    if not sig_header or not sig_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header[7:])


async def _send_message(recipient_id: str, text: str) -> None:
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text[:2000]},  # Messenger hard limit 2000 chars
        "messaging_type": "RESPONSE",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            MESSENGER_API,
            params={"access_token": _page_token()},
            json=payload,
        )
    if r.status_code != 200:
        logger.error("Messenger send failed %s: %s", r.status_code, r.text)


async def _send_typing(recipient_id: str, on: bool) -> None:
    action = "typing_on" if on else "typing_off"
    payload = {"recipient": {"id": recipient_id}, "sender_action": action}
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(
            MESSENGER_API,
            params={"access_token": _page_token()},
            json=payload,
        )


async def _handle_message(text: str, sender_id: str, request: Request) -> None:
    retriever = request.app.state.retriever
    extractor = request.app.state.extractor

    await _send_typing(sender_id, True)
    try:
        entities = await asyncio.to_thread(extractor.extract, text)
        country = entities.get("country")
        category = entities.get("category")

        chunks = await asyncio.to_thread(
            retriever.search, text, country, category, 5
        )
        context = build_context(chunks)

        from openai import OpenAI
        import random

        def _pick_key() -> str:
            keys_str = os.environ.get("DEEPSEEK_API_KEYS", "")
            keys = [k.strip() for k in keys_str.split(",") if k.strip()]
            return random.choice(keys) if keys else os.environ["DEEPSEEK_API_KEY"]

        def _call_llm() -> str:
            client = OpenAI(
                api_key=_pick_key(),
                base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            )
            resp = client.chat.completions.create(
                model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": f"Context:\n{context}\n\nCâu hỏi: {text}"},
                ],
                temperature=0.3,
                max_tokens=512,
            )
            return resp.choices[0].message.content.strip()

        answer = await asyncio.to_thread(_call_llm)

        # Append source URLs if any
        urls = [c["source_url"] for c in chunks if c.get("source_url")]
        if urls:
            unique_urls = list(dict.fromkeys(urls))[:3]
            sources_text = "\n\nNguồn:\n" + "\n".join(f"• {u}" for u in unique_urls)
            if len(answer) + len(sources_text) <= 2000:
                answer += sources_text

        await _send_typing(sender_id, False)
        await _send_message(sender_id, answer)

    except Exception:
        logger.exception("Error handling Messenger message from %s", sender_id)
        await _send_typing(sender_id, False)
        await _send_message(
            sender_id,
            "Xin lỗi, hiện tại tôi đang gặp sự cố. Vui lòng thử lại sau hoặc liên hệ L&C Global trực tiếp.",
        )


# ── routes ───────────────────────────────────────────────────────────────────

@router.get("", response_class=PlainTextResponse)
async def verify_webhook(request: Request) -> str:
    """Facebook calls this to verify the webhook URL."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    verify_token = os.environ.get("FB_VERIFY_TOKEN", "")
    if mode == "subscribe" and token == verify_token:
        logger.info("Facebook webhook verified")
        return challenge or ""
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def receive_webhook(request: Request) -> dict:
    """Receive events from Facebook Messenger."""
    body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256")
    if not _verify_signature(body, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")

    data = await request.json()
    if data.get("object") != "page":
        return {"status": "ignored"}

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id: str = event["sender"]["id"]
            msg = event.get("message", {})

            # Ignore echoes (messages sent by the page itself)
            if msg.get("is_echo"):
                continue

            text: str | None = msg.get("text")
            if text:
                # Fire-and-forget — respond to Facebook immediately (< 5s timeout)
                asyncio.create_task(_handle_message(text, sender_id, request))

    return {"status": "ok"}
