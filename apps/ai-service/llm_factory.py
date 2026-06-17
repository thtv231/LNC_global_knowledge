"""Returns the best available LLM: DeepSeek (with key rotation) first, Groq as fallback."""
import itertools
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from config import settings

# Build key pool: DEEPSEEK_API_KEYS (comma-separated) takes priority, then DEEPSEEK_API_KEY
def _build_key_pool() -> list[str]:
    if settings.deepseek_api_keys:
        keys = [k.strip() for k in settings.deepseek_api_keys.split(",") if k.strip()]
        if keys:
            return keys
    if settings.deepseek_api_key:
        return [settings.deepseek_api_key]
    return []

_key_pool = _build_key_pool()
_key_cycle = itertools.cycle(_key_pool) if _key_pool else None


def _next_deepseek_key() -> str | None:
    if _key_cycle is None:
        return None
    return next(_key_cycle)


def get_llm(temperature: float = 0.3, max_tokens: int = 2048, streaming: bool = True):
    key = _next_deepseek_key()
    if key:
        return ChatOpenAI(
            model=settings.deepseek_model,
            api_key=key,
            base_url="https://api.deepseek.com",
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            timeout=110,
            max_retries=1,
        )
    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
    )


def get_fast_llm(temperature: float = 0, max_tokens: int = 200):
    """Lightweight LLM for entity extraction."""
    key = _next_deepseek_key()
    if key:
        return ChatOpenAI(
            model=settings.deepseek_model,
            api_key=key,
            base_url="https://api.deepseek.com",
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=False,
        )
    return ChatGroq(
        model=settings.groq_suggest_model,
        api_key=settings.groq_api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=False,
    )
