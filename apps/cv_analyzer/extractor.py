from __future__ import annotations
import os
import json
import logging
from groq import Groq
from apps.cv_analyzer.schemas import ImmigrationProfileSchema

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Bạn là chuyên gia phân tích CV cho mục đích định cư Mỹ (EB-1A, EB-2 NIW).
Nhiệm vụ: trích xuất thông tin từ CV sang JSON theo schema được cung cấp.

CRITICAL RULES:
1. Chỉ trích xuất thông tin CÓ TRONG CV, không suy diễn hay thêm thông tin
2. Với publications: ghi đầy đủ tên bài báo, journal/conference, năm
3. Với awards: ghi tên giải, tổ chức trao, năm
4. Với work_history.main_responsibilities: giữ nguyên chi tiết kỹ thuật,
   đây là dữ liệu quan trọng để map SOC code
5. Tính age dựa trên năm hiện tại là 2026
6. Trả về JSON hợp lệ theo schema, không có text ngoài JSON

Schema JSON cần trả về:
{
  "full_name": "string",
  "age": null or int,
  "current_country": null or "string",
  "language_skills": [],
  "education_history": [
    {
      "degree_level": "Doctorate (PhD)" | "Master's Degree" | "Post-Graduate Diploma/Certificate" | "Bachelor's Degree" | "Two-Year College/Technical Diploma" | "High School Graduation" | "Other/Unspecified",
      "field_of_study": "string",
      "institution": "string",
      "country": "string",
      "start_date": null or "YYYY" or "YYYY-MM",
      "end_date": null or "YYYY" or "YYYY-MM" or "Present"
    }
  ],
  "work_history": [
    {
      "job_title": "string",
      "company": "string",
      "country": "string",
      "start_date": "YYYY-MM",
      "end_date": "YYYY-MM" or "Present",
      "is_full_time": true,
      "main_responsibilities": ["string", ...]
    }
  ],
  "certifications": [],
  "publications": ["Full citation string", ...],
  "awards": ["Award name, Organization, Year", ...],
  "patents": [],
  "media_coverage": [],
  "speaking_engagements": [],
  "memberships": []
}"""


async def extract_profile(markdown_text: str) -> ImmigrationProfileSchema:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    truncated = markdown_text[:12000]

    response = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama3-70b-8192"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract this CV:\n\n{truncated}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=4096,
    )

    raw_json = response.choices[0].message.content
    logger.info("Groq extraction complete, validating schema...")
    profile = ImmigrationProfileSchema.model_validate_json(raw_json)
    return profile
