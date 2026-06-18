from __future__ import annotations

import logging

from apps.cv_analyzer import deepseek_client as ds
from apps.cv_analyzer.schemas import ImmigrationProfileSchema, USAScoreResult

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Bạn là Luật sư Di trú Cao cấp chuyên về diện EB-1A (Extraordinary Ability) \
và EB-2 NIW (National Interest Waiver) tại Mỹ.

Nhiệm vụ: nhận dữ liệu hồ sơ JSON và kết quả chấm điểm, phân tích gap và \
đưa ra lộ trình cụ thể để tối ưu hồ sơ.

CHAIN-OF-THOUGHT RULE: Trước khi kết luận, BẮT BUỘC phân tích từng bước \
trong thẻ <lawyer_thinking>:
1. Đánh giá từng tiêu chí EB-1A: đạt/chưa đạt và lý do cụ thể
2. Phân tích 3 Prong của EB-2 NIW: điểm mạnh và điểm yếu từng prong
3. So sánh: EB-1A hay EB-2 NIW phù hợp hơn với profile này?
4. Xác định 2-3 hành động có thể thực hiện ngay trong 6-12 tháng tới

Sau thẻ tư duy, xuất báo cáo theo cấu trúc markdown bắt buộc sau đây.
Viết bằng tiếng Việt. Không bịa đặt thông tin không có trong hồ sơ."""

_USER_TEMPLATE = """\
## Dữ liệu hồ sơ ứng viên:
{profile_json}

## Kết quả chấm điểm sơ bộ:
- EB-1A: Đạt {eb1a_met}/10 tiêu chí → {eb1a_status}
  Tiêu chí đạt: {eb1a_criteria_met}
  Tiêu chí chưa đạt: {eb1a_criteria_missing}

- EB-2 NIW: Tổng {eb2niw_total}/9 điểm → {eb2niw_status}
  Prong 1 (Merit & National Importance): {prong1}/3
  Prong 2 (Well Positioned): {prong2}/3
  Prong 3 (Beneficial to Waive): {prong3}/3

- Tổng kinh nghiệm: {exp_months} tháng ({exp_years:.1f} năm)
- Khuyến nghị sơ bộ: {recommended}

Hãy phân tích chi tiết và xuất báo cáo theo cấu trúc sau:

<lawyer_thinking>
[Phân tích CoT chi tiết ở đây — bắt buộc]
</lawyer_thinking>

## Tổng quan hồ sơ

## Khuyến nghị chương trình
**Chương trình phù hợp nhất:** [EB-1A / EB-2 NIW / Cả hai]
**Lý do:** [giải thích ngắn]

## EB-1A — Phân tích tiêu chí
### ✅ Tiêu chí đã đạt
### ❌ Tiêu chí chưa đạt

## EB-2 NIW — Phân tích 3 Prong
### Prong 1: Substantial Merit & National Importance
### Prong 2: Well Positioned to Advance
### Prong 3: Beneficial to Waive Job Offer Requirement

## Điểm mạnh cần khai thác

## Rào cản lớn nhất (Bottlenecks)

## Lộ trình hành động
### Ngắn hạn (0-3 tháng)
### Trung hạn (3-12 tháng)
### Dài hạn (12+ tháng)
"""


async def generate_gap_analysis(
    profile: ImmigrationProfileSchema,
    scores: USAScoreResult,
) -> str:
    """
    Gọi DeepSeek với CoT để tạo báo cáo gap analysis dạng markdown.
    """
    profile_json = profile.model_dump_json(indent=2)

    user_content = _USER_TEMPLATE.format(
        profile_json=profile_json,
        eb1a_met=scores.eb1a_total_met,
        eb1a_status="ĐỦ ĐIỀU KIỆN" if scores.eb1a_eligible else "CHƯA ĐỦ",
        eb1a_criteria_met=", ".join(scores.eb1a_criteria_met) or "Không có",
        eb1a_criteria_missing=", ".join(scores.eb1a_criteria_missing) or "Không có",
        eb2niw_total=scores.eb2niw_total_score,
        eb2niw_status="ĐỦ ĐIỀU KIỆN" if scores.eb2niw_eligible else "CHƯA ĐỦ",
        prong1=scores.eb2niw_prong1_score,
        prong2=scores.eb2niw_prong2_score,
        prong3=scores.eb2niw_prong3_score,
        exp_months=scores.experience_months,
        exp_years=scores.experience_months / 12,
        recommended=scores.recommended_program,
    )

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    gap_report = await ds.chat(
        messages,
        temperature=0.3,   # cho phép reasoning linh hoạt hơn extraction
        max_tokens=6000,
    )

    logger.info(f"Gap report generated: {len(gap_report)} chars")
    return gap_report
