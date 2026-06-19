from __future__ import annotations
import os
import asyncio
import logging
from typing import List
from openai import AsyncOpenAI
from apps.cv_analyzer.schemas import ImmigrationProfileSchema, USAScoreResult, SimilarCase

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Bạn là Luật sư Di trú Cao cấp chuyên về diện EB-1A (Extraordinary Ability) \
và EB-2 NIW (National Interest Waiver) tại Mỹ.

Nhiệm vụ: nhận dữ liệu hồ sơ JSON và kết quả chấm điểm, phân tích gap và \
đưa ra lộ trình cụ thể để tối ưu hồ sơ.

CHAIN-OF-THOUGHT RULE: Trước khi kết luận, BẮT BUỘC phân tích từng bước \
trong thẻ <lawyer_thinking>:
1. Đánh giá từng tiêu chí EB-1A: đạt/chưa đạt và lý do cụ thể
2. Phân tích 3 Prong của EB-2 NIW: điểm mạnh và điểm yếu từng prong
3. So sánh: EB-1A hay EB-2 NIW phù hợp hơn với profile này?
4. Xác định 2-3 hành động có thể thực hiện ngay trong 6-12 tháng tới

Sau thẻ tư duy, xuất báo cáo theo cấu trúc bắt buộc."""


def _format_similar_cases(cases: List[SimilarCase]) -> str:
    if not cases:
        return "(Không tìm thấy case tương tự trong database)"
    lines = []
    for i, c in enumerate(cases, 1):
        rfe_note = " ⚠️ Bị RFE trước khi approve" if c.post_rfe else ""
        lines.append(
            f"Case #{i} ({c.program} - {c.field}):{rfe_note}\n"
            f"  - Bằng cấp: {c.degree} | Vai trò: {c.current_role}\n"
            f"  - Publications: {c.publications} | Citations: {c.citations}\n"
            f"  - Thư giới thiệu: {c.recommendation_letters}\n"
            f"  - Xử lý: {c.processing_days:.0f} ngày ({c.premium_processing})\n"
            f"  - Similarity score: {c.similarity_score:.2f}/1.0\n"
            f"  - Notable: {c.notable}\n"
            f"  - Nguồn: {c.source_url}"
        )
    return "\n\n".join(lines)


def _build_user_prompt(
    profile: ImmigrationProfileSchema,
    scores: USAScoreResult,
    similar_cases: List[SimilarCase],
) -> str:
    profile_json = profile.model_dump_json(indent=2)
    cases_text = _format_similar_cases(similar_cases)

    return f"""## Dữ liệu hồ sơ ứng viên:
{profile_json}

## Kết quả chấm điểm sơ bộ:
- EB-1A: Đạt {scores.eb1a_total_met}/10 tiêu chí → {"ĐỦ ĐIỀU KIỆN" if scores.eb1a_eligible else "CHƯA ĐỦ"}
  Tiêu chí đạt: {", ".join(scores.eb1a_criteria_met) or "Không có"}
  Tiêu chí chưa đạt: {", ".join(scores.eb1a_criteria_missing)}

- EB-2 NIW: Tổng {scores.eb2niw_total_score}/9 điểm → {"ĐỦ ĐIỀU KIỆN" if scores.eb2niw_eligible else "CHƯA ĐỦ"}
  Prong 1 (Merit): {scores.eb2niw_prong1_score}/3
  Prong 2 (Positioned): {scores.eb2niw_prong2_score}/3
  Prong 3 (Beneficial): {scores.eb2niw_prong3_score}/3

- Tổng kinh nghiệm: {scores.experience_months} tháng

## Hồ sơ tương tự đã được APPROVE (từ database thực tế):

{cases_text}

Dựa trên các case đã approve này, hãy:
1. Chỉ ra profile hiện tại đang ở mức nào so với các case đã pass
2. Cụ thể hóa khoảng cách (gap) bằng CON SỐ thực tế
3. Nếu case tương tự bị RFE nhưng vẫn pass → cảnh báo rủi ro RFE

Hãy phân tích và xuất báo cáo theo cấu trúc bắt buộc:

<lawyer_thinking>
[phân tích CoT chi tiết ở đây]
</lawyer_thinking>

## Tổng quan hồ sơ
## Khuyến nghị chương trình
## EB-1A — Phân tích tiêu chí
### ✅ Tiêu chí đã đạt
### ❌ Tiêu chí chưa đạt
## EB-2 NIW — Phân tích 3 Prong
### Prong 1: Substantial Merit & National Importance
### Prong 2: Well Positioned to Advance
### Prong 3: Beneficial to Waive Job Offer Requirement
## Điểm mạnh cần khai thác (Strong Points)
## Rào cản lớn nhất (Bottlenecks)
## Lộ trình hành động (Actionable Roadmap)
### Ngắn hạn (0-3 tháng)
### Trung hạn (3-12 tháng)
### Dài hạn (12+ tháng)"""


async def _call_deepseek_with_retry(prompt: str, max_retries: int = 3) -> str:
    client = AsyncOpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=8192,
            )
            return response.choices[0].message.content
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = 2 ** (attempt + 1)
            logger.warning(f"DeepSeek attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)


async def generate_gap_analysis(
    profile: ImmigrationProfileSchema,
    scores: USAScoreResult,
    similar_cases: List[SimilarCase],
) -> str:
    prompt = _build_user_prompt(profile, scores, similar_cases)
    logger.info("Calling DeepSeek for gap analysis...")
    result = await _call_deepseek_with_retry(prompt)
    logger.info("Gap analysis complete")
    return result
