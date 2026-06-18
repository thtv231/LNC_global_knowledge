from langchain_groq import ChatGroq
from config import settings
from graph.state import ChatState
import json
import re

llm = ChatGroq(
    model=settings.groq_suggest_model,
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
