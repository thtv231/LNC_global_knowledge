from graph.state import ChatState
from llm_factory import get_fast_llm
import json
import re

PROMPT = """Dựa vào câu hỏi và câu trả lời về định cư dưới đây, tạo đúng 3 câu hỏi tiếp theo ngắn gọn mà người dùng có thể muốn hỏi thêm.

Câu hỏi gốc: {query}
Câu trả lời: {answer}

Yêu cầu:
- Đúng 3 câu hỏi, bằng tiếng Việt
- Mỗi câu hỏi dưới 15 từ, cụ thể và liên quan trực tiếp đến chủ đề vừa thảo luận
- KHÔNG hỏi lại điều đã được trả lời
- Trả về JSON array, không có markdown, không giải thích gì thêm

Ví dụ format: ["Câu hỏi 1?", "Câu hỏi 2?", "Câu hỏi 3?"]"""


def generate_suggestions(state: ChatState) -> dict:
    answer = state.get("answer", "")
    query = state.get("query", "")

    if not answer or len(query) < 5:
        return {"suggestions": []}

    try:
        llm = get_fast_llm(temperature=0.6, max_tokens=300)
        result = llm.invoke(PROMPT.format(query=query, answer=answer[:500]))
        raw = result.content.strip()
        raw = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.DOTALL)
        match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if match:
            suggestions = json.loads(match.group())
            if isinstance(suggestions, list) and len(suggestions) > 0:
                return {"suggestions": [s for s in suggestions[:3] if isinstance(s, str)]}
    except Exception:
        pass

    # Fallback: generic follow-up questions based on topic
    country = state.get("country")
    if country == "canada":
        return {"suggestions": [
            "Điều kiện cụ thể để đủ điều kiện là gì?",
            "Quy trình nộp hồ sơ mất bao lâu?",
            "Chi phí tổng thể cho chương trình này là bao nhiêu?",
        ]}
    if country == "usa":
        return {"suggestions": [
            "Tỷ lệ approval của chương trình này là bao nhiêu?",
            "Cần chuẩn bị những tài liệu gì?",
            "Mất bao lâu từ nộp đến nhận kết quả?",
        ]}
    return {"suggestions": [
        "Điều kiện cụ thể là gì?",
        "Quy trình nộp hồ sơ như thế nào?",
        "Chi phí dự kiến là bao nhiêu?",
    ]}
