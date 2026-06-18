"""Returns the best available LLM: Groq first, DeepSeek as fallback."""
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from config import settings


def get_llm(temperature: float = 0.3, max_tokens: int = 2048, streaming: bool = True):
    if settings.deepseek_api_key:
        return ChatOpenAI(
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
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
    if settings.deepseek_api_key:
        return ChatOpenAI(
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
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
