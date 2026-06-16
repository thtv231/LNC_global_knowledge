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
    web_chunks: list[dict]       # từ Tavily web search (real-time)
    merged_chunks: list[dict]    # sau khi merge + rank

    # Output
    answer: str
    sources: list[dict]          # [{title, source_url, category, country}]
    suggestions: list[str]       # 3 câu hỏi gợi ý tiếp theo
    stream_tokens: Annotated[list[str], operator.add]
