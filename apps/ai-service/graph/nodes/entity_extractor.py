from langchain_core.prompts import ChatPromptTemplate
from graph.state import ChatState
from llm_factory import get_fast_llm
import json
import re

SYSTEM = """Bạn là bộ phân tích câu hỏi định cư. Đọc câu hỏi và trích xuất 3 trường sau.

Trả về JSON hợp lệ duy nhất, không có markdown hay giải thích:
{{
  "country": "canada" | "usa" | "newzealand" | null,
  "category": <xem danh sách bên dưới> | null,
  "topic": <chủ đề cốt lõi, tối đa 6 từ tiếng Anh>
}}

DANH SÁCH CATEGORY HỢP LỆ:

Canada:
- "Express-Entry"     → hệ thống điểm CRS, FSW, CEC, FST
- "PNP"               → Provincial Nominee Program, định cư tỉnh bang
- "LMIA"              → Labour Market Impact Assessment, giấy phép tuyển lao động nước ngoài
- "TFWP"              → Temporary Foreign Worker Program, lao động tạm thời
- "study-permit"      → giấy phép du học Canada
- "work-permit"       → giấy phép làm việc Canada (không thuộc TFWP)
- "family-sponsorship"→ bảo lãnh gia đình, đoàn tụ gia đình Canada
- "citizenship"       → nhập tịch, quốc tịch Canada
- "permanent_residence" → thường trú nhân Canada (general)

USA:
- "EB1-A"             → tài năng đặc biệt (extraordinary ability)
- "EB1-B"             → giáo sư / nhà nghiên cứu xuất sắc
- "EB1-C"             → quản lý / giám đốc đa quốc gia
- "EB2-NIW"           → miễn yêu cầu việc làm vì lợi ích quốc gia
- "EB3"               → lao động có tay nghề, lao động phổ thông
- "L1-Visa"           → chuyển nhượng nội bộ công ty
- "H1B"               → visa lao động chuyên môn cao
- "O1-Visa"           → tài năng đặc biệt ngắn hạn
- "F1-Visa"           → du học sinh Mỹ
- "naturalization"    → nhập tịch Mỹ
- "green-card"        → thẻ xanh / thường trú nhân Mỹ (general)

New Zealand:
- "skilled-migrant"   → Skilled Migrant Category, hệ thống điểm NZ
- "accredited-employer" → Accredited Employer Work Visa (AEWV)
- "investor-visa"     → đầu tư định cư NZ
- "family-visa"       → đoàn tụ gia đình NZ
- "student-visa"      → du học NZ
- "citizenship-nz"    → nhập tịch New Zealand

QUY TẮC:
- Nếu câu hỏi nhắc đến từ khoá nào khớp với category, dùng category đó
- Nếu câu hỏi hỏi CHUNG về một nước ("tìm hiểu định cư Canada", "muốn sang Mỹ", "định cư New Zealand") → country đúng, category = null (KHÔNG dùng "permanent_residence" hay "green-card" cho câu hỏi chung)
- "permanent_residence" CHỈ dùng khi user hỏi cụ thể về thẻ PR / PR card / bước sau khi có PR
- "green-card" CHỈ dùng khi user hỏi cụ thể về green card Mỹ sau khi có visa
- **Nếu câu hỏi không đề cập quốc gia nhưng lịch sử chat đã rõ** → kế thừa country từ lịch sử
- Nếu không xác định được country hoặc category → trả null (đừng đoán)
- topic phải phản ánh đúng điều user muốn biết (ví dụ: "CRS score requirements 2024", "NIW petition steps")

TỪ KHOÁ ĐẶC TRƯNG (không cần nhắc tên nước vẫn nhận ra):
- Canada: "tỉnh bang", "bảo lãnh tỉnh bang", "PNP", "Express Entry", "CRS", "IRCC", "NOC", "LMIA", "WES", "CLB", "FSW", "CEC"
- USA: "USCIS", "I-140", "I-485", "green card", "NIW", "EB-1", "EB-2", "H-1B", "visa bulletin", "priority date"
- New Zealand: "INZ", "Skilled Migrant", "AEWV", "Immigration NZ", "SMC points\""""

llm = get_fast_llm(temperature=0, max_tokens=200)

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM),
    ("human", "{query}"),
])

chain = prompt | llm


def extract_entities(state: ChatState) -> dict:
    # Include last 2 turns of history so extractor can infer country from context
    history = state.get("history", [])[-4:]
    history_lines = []
    for h in history:
        role = "Người dùng" if h["role"] == "user" else "Bot"
        history_lines.append(f"{role}: {h['content'][:150]}")

    # Hint about known country from session
    known_country = state.get("country")  # pre-seeded from session last_country
    country_hint = f"\n[Quốc gia đang thảo luận: {known_country}]" if known_country else ""

    if history_lines:
        query_input = f"[Lịch sử]\n{chr(10).join(history_lines)}{country_hint}\n\n[Câu hỏi]\n{state['query']}"
    else:
        query_input = f"{country_hint}\n{state['query']}".strip() if country_hint else state["query"]

    result = chain.invoke({"query": query_input})
    raw = result.content.strip()
    raw = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.DOTALL)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"country": None, "category": None, "topic": state["query"][:50]}

    # If LLM couldn't determine country, keep the session's known country
    extracted_country = data.get("country") or known_country
    return {
        "country":  extracted_country,
        "category": data.get("category") or state.get("category"),
        "topic":    data.get("topic", ""),
    }
