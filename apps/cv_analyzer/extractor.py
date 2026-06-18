from __future__ import annotations

import json
import logging

from apps.cv_analyzer import deepseek_client as ds
from apps.cv_analyzer.schemas import ImmigrationProfileSchema

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Bạn là chuyên gia phân tích CV cho mục đích định cư Mỹ (EB-1A, EB-2 NIW).
Nhiệm vụ: trích xuất thông tin từ CV sang JSON theo schema được cung cấp.

CRITICAL RULES:
1. Chỉ trích xuất thông tin CÓ TRONG CV, không suy diễn hay thêm thông tin
2. Với publications: ghi đầy đủ tên bài báo, journal/conference, năm
3. Với awards: ghi tên giải, tổ chức trao, năm
4. Với work_history.main_responsibilities: giữ nguyên chi tiết kỹ thuật,
   đây là dữ liệu quan trọng để map SOC code
5. Tính age dựa trên năm hiện tại là 2026
6. start_date và end_date theo format YYYY-MM hoặc YYYY, end_date dùng "Present" nếu đang làm/học
7. Trả về JSON hợp lệ theo schema, không có text ngoài JSON

JSON Schema cần trả về:
{
  "full_name": "string",
  "age": null hoặc integer,
  "current_country": null hoặc "string",
  "language_skills": [{"test_type": "IELTS|PTE Academic|CELPIP|TEF (French)|TCF (French)|Not Mentioned", "overall": null|float, "listening": null|float, "reading": null|float, "writing": null|float, "speaking": null|float}],
  "education_history": [{"degree_level": "Doctorate (PhD)|Master's Degree|Post-Graduate Diploma/Certificate|Bachelor's Degree|Two-Year College/Technical Diploma|High School Graduation|Other/Unspecified", "field_of_study": "string", "institution": "string", "country": "string", "start_date": null|"YYYY-MM", "end_date": null|"YYYY-MM|Present"}],
  "work_history": [{"job_title": "string", "company": "string", "country": "string", "start_date": "YYYY-MM", "end_date": "YYYY-MM|Present", "is_full_time": true|false, "main_responsibilities": ["string"]}],
  "certifications": ["string"],
  "publications": ["string"],
  "awards": ["string"],
  "patents": ["string"],
  "media_coverage": ["string"],
  "speaking_engagements": ["string"],
  "memberships": ["string"]
}"""


async def extract_profile(markdown_text: str) -> ImmigrationProfileSchema:
    """
    Gọi DeepSeek với JSON mode để trích xuất ImmigrationProfileSchema từ markdown CV.
    Toàn bộ CV được nạp một lượt, không chunk.
    """
    # Giới hạn input để tránh vượt context window DeepSeek (~32k tokens)
    truncated = markdown_text[:24_000]
    if len(markdown_text) > 24_000:
        logger.warning(f"CV text truncated from {len(markdown_text)} to 24000 chars")

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"Trích xuất thông tin từ CV sau:\n\n{truncated}"},
    ]

    raw_json = await ds.chat(
        messages,
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=4096,
    )

    logger.info(f"Extractor received {len(raw_json)} chars of JSON")

    try:
        profile = ImmigrationProfileSchema.model_validate_json(raw_json)
    except Exception as e:
        # DeepSeek đôi khi trả về JSON với field bị null không khớp schema
        # Thử parse thủ công để có error message rõ hơn
        logger.error(f"Schema validation failed: {e}\nRaw JSON (first 500 chars): {raw_json[:500]}")
        raise ValueError(f"Không parse được kết quả từ DeepSeek: {e}") from e

    return profile
