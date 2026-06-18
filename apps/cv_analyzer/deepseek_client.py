from __future__ import annotations

import asyncio
import itertools
import logging
import os
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI, RateLimitError

logger = logging.getLogger(__name__)

_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_DEEPSEEK_MODEL = "deepseek-chat"


def _load_keys() -> List[str]:
    keys: List[str] = []
    primary = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if primary:
        keys.append(primary)
    extras = os.getenv("DEEPSEEK_API_KEYS", "")
    for k in extras.split(","):
        k = k.strip()
        if k and k not in keys:
            keys.append(k)
    if not keys:
        raise RuntimeError("No DeepSeek API keys found. Set DEEPSEEK_API_KEY or DEEPSEEK_API_KEYS.")
    logger.info(f"DeepSeek key pool: {len(keys)} key(s) loaded")
    return keys


_key_pool = _load_keys()
_key_cycle = itertools.cycle(_key_pool)


def _get_client() -> AsyncOpenAI:
    key = next(_key_cycle)
    return AsyncOpenAI(
        api_key=key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", _DEEPSEEK_BASE_URL),
    )


async def chat(
    messages: List[Dict[str, str]],
    *,
    response_format: Optional[Dict[str, str]] = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    max_retries: int = 3,
) -> str:
    """
    Gọi DeepSeek với round-robin key rotation và retry khi rate limit.
    Trả về nội dung text của assistant message.
    """
    last_err: Exception = RuntimeError("No attempt made")
    delay = 2.0

    for attempt in range(max_retries):
        try:
            client = _get_client()
            kwargs: Dict[str, Any] = {
                "model": os.getenv("DEEPSEEK_MODEL", _DEEPSEEK_MODEL),
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format:
                kwargs["response_format"] = response_format

            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""

        except RateLimitError as e:
            last_err = e
            logger.warning(f"DeepSeek rate limit (attempt {attempt + 1}/{max_retries}), retry in {delay}s")
            await asyncio.sleep(delay)
            delay *= 2
        except Exception as e:
            last_err = e
            logger.error(f"DeepSeek error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
                delay *= 2

    raise last_err
