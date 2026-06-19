"""CV analysis: parse → DeepSeek extract → deterministic score → DeepSeek gap.

All LLM calls go through llm_factory._next_deepseek_key() key-rotation loop.
No dependency on api/routes/cv.py or the case-matcher (no 15 MB file load).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import date
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from openai import AsyncOpenAI

from config import settings
from llm_factory import _next_deepseek_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cv", tags=["CV Analyzer"])

ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# ── Prompts ───────────────────────────────────────────────────────────────────

_EXTRACT_SYSTEM = """\
Bạn là chuyên gia phân tích CV định cư Mỹ (EB-1A, EB-2 NIW).
Trích xuất thông tin từ CV sang JSON theo schema sau. Chỉ trích xuất thông tin
CÓ TRONG CV, không suy diễn. Năm hiện tại là 2026.
Trả về JSON hợp lệ, không có text hay markdown fence ngoài JSON.

SCHEMA:
{
  "full_name": "string",
  "age": null | int,
  "current_country": null | "string",
  "education_history": [
    {"degree_level": "Doctorate (PhD)"|"Master's Degree"|"Bachelor's Degree"|"Other",
     "field_of_study": "string", "institution": "string", "country": "string",
     "start_date": null|"YYYY", "end_date": null|"YYYY"|"Present"}
  ],
  "work_history": [
    {"job_title": "string", "company": "string", "country": "string",
     "start_date": "YYYY-MM", "end_date": "YYYY-MM"|"Present",
     "is_full_time": true|false,
     "main_responsibilities": ["string"]}
  ],
  "publications": ["full citation string"],
  "awards": ["Award name, Organization, Year"],
  "patents": [],
  "media_coverage": [],
  "speaking_engagements": [],
  "memberships": []
}"""

_GAP_SYSTEM = """\
Bạn là Luật sư Di trú Cao cấp chuyên EB-1A và EB-2 NIW tại Mỹ.

CHAIN-OF-THOUGHT: Trước khi kết luận BẮT BUỘC phân tích trong thẻ <lawyer_thinking>:
1. Đánh giá từng tiêu chí EB-1A: đạt/chưa đạt và lý do
2. Phân tích 3 Prong EB-2 NIW: điểm mạnh/yếu từng prong
3. So sánh: EB-1A hay EB-2 NIW phù hợp hơn?
4. 2-3 hành động có thể làm ngay trong 6-12 tháng

Sau thẻ tư duy, xuất báo cáo theo cấu trúc:
## Tổng quan hồ sơ
## Khuyến nghị chương trình
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
### Dài hạn (12+ tháng)"""


# ── DeepSeek helper with key-rotation retry loop ──────────────────────────────

async def _deepseek(
    system: str,
    user: str,
    *,
    json_mode: bool = False,
    max_tokens: int = 4096,
    temperature: float = 0.1,
) -> str:
    """Call DeepSeek, cycling through the key pool on failure."""
    n_keys = max(1, len(settings.deepseek_api_keys.split(",")) if settings.deepseek_api_keys else 1)
    max_attempts = n_keys * 2  # try each key twice before giving up

    last_err: Exception | None = None
    for attempt in range(max_attempts):
        key = _next_deepseek_key()
        if not key:
            raise HTTPException(500, "Chưa cấu hình DEEPSEEK_API_KEY")
        try:
            client = AsyncOpenAI(
                api_key=key,
                base_url="https://api.deepseek.com",
                timeout=120,
            )
            kwargs: dict = dict(
                model=settings.deepseek_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            resp = await client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content

        except Exception as e:
            last_err = e
            delay = 2 ** min(attempt, 4)
            logger.warning(f"DeepSeek attempt {attempt + 1}/{max_attempts} failed: {e} — retry in {delay}s")
            await asyncio.sleep(delay)

    raise HTTPException(500, f"DeepSeek failed after {max_attempts} attempts: {last_err}")


# ── PDF/DOCX parser ───────────────────────────────────────────────────────────

def _parse_pdf(pdf_bytes: bytes) -> str:
    import pymupdf
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    parts = [page.get_text("text") for page in doc]
    doc.close()
    return "\n\n".join(parts)


def _parse_docx(docx_bytes: bytes) -> str:
    from io import BytesIO
    import docx as python_docx
    doc = python_docx.Document(BytesIO(docx_bytes))
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            lines.append("")
            continue
        style = para.style.name.lower()
        if "heading 1" in style:
            lines.append(f"# {text}")
        elif "heading 2" in style:
            lines.append(f"## {text}")
        elif "heading 3" in style:
            lines.append(f"### {text}")
        elif "list" in style:
            lines.append(f"- {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


async def _parse(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    loop = asyncio.get_event_loop()
    if ext == ".docx":
        return await loop.run_in_executor(None, _parse_docx, file_bytes)
    if ext == ".pdf":
        text = await loop.run_in_executor(None, _parse_pdf, file_bytes)
        if len(text) < 200:
            raise HTTPException(422, "PDF quá ít text — thử chuyển sang DOCX hoặc dùng PDF không scan.")
        return text
    raise HTTPException(400, f"Định dạng không hỗ trợ: {ext}. Chỉ chấp nhận PDF hoặc DOCX.")


# ── Deterministic scoring (no LLM needed) ────────────────────────────────────

_JUDGE_KW = {"reviewer", "review", "judge", "peer review", "editorial board", "phản biện", "đánh giá"}
_LEAD_KW  = {"director", "head", "lead", "chief", "founder", "vp", "president", "manager",
             "giám đốc", "trưởng", "phó", "trưởng nhóm"}
_ART_KW   = {"exhibition", "gallery", "exhibit", "showcase", "triển lãm"}
_SAL_KW   = {"salary", "high earning", "top percentile", "lương cao", "compensation"}
_STEM_KW  = {"computer", "software", "engineering", "physics", "chemistry", "biology",
             "biotech", "mathematics", "data", "artificial intelligence", "machine learning",
             "medicine", "healthcare", "energy", "defense", "aerospace", "robotics"}
_STRAT_KW = {"artificial intelligence", "ai", "machine learning", "biotech", "biotechnology",
             "energy", "defense", "aerospace", "quantum", "cybersecurity", "genomics"}


def _kw_match(texts: list[str], kw: set[str]) -> bool:
    combined = " ".join(texts).lower()
    return any(k in combined for k in kw)


def _experience_months(work_history: list[dict]) -> int:
    def _parse_date(s: str) -> date:
        s = s.strip()
        if s.lower() == "present":
            return date.today()
        parts = s.split("-")
        return date(int(parts[0]), int(parts[1]) if len(parts) > 1 else 1, 1)

    full_iv, part_iv = [], []
    for job in work_history:
        try:
            s = _parse_date(job.get("start_date", ""))
            e = _parse_date(job.get("end_date", ""))
            if e >= s:
                (full_iv if job.get("is_full_time", True) else part_iv).append((s, e))
        except Exception:
            pass

    def _iv_months(ivs: list) -> int:
        if not ivs:
            return 0
        ivs = sorted(ivs)
        merged = [list(ivs[0])]
        for s, e in ivs[1:]:
            if s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        return sum((e.year - s.year) * 12 + (e.month - s.month) for s, e in merged)

    return _iv_months(full_iv) + _iv_months(part_iv) // 2


def _score(profile: dict) -> dict:
    responsibilities = [
        r
        for job in profile.get("work_history", [])
        for r in (job.get("main_responsibilities") or [])
    ] + [job.get("job_title", "") for job in profile.get("work_history", [])]

    pubs    = profile.get("publications") or []
    awards  = profile.get("awards") or []
    patents = profile.get("patents") or []
    meds    = profile.get("media_coverage") or []
    members = profile.get("memberships") or []

    # ── EB-1A (need ≥3 of 10) ────────────────────────────────────────────────
    eb1a_criteria = {
        "Awards/Prizes xuất sắc":                     bool(awards),
        "Membership hội nghề nghiệp uy tín":           bool(members),
        "Media coverage về công việc":                 bool(meds),
        "Đánh giá công trình người khác (Reviewer)":  _kw_match(responsibilities, _JUDGE_KW),
        "Original contributions (Publications/Patents)": bool(pubs) or bool(patents),
        "Bài báo journal/conference":                  bool(pubs),
        "Triển lãm tác phẩm nghệ thuật":              _kw_match(responsibilities, _ART_KW),
        "Vai trò lãnh đạo/Critical trong tổ chức":    _kw_match(responsibilities, _LEAD_KW),
        "Mức lương cao hơn peers":                    _kw_match(responsibilities, _SAL_KW),
        "Thành công thương mại nghệ thuật":           False,
    }
    met     = [k for k, v in eb1a_criteria.items() if v]
    missing = [k for k, v in eb1a_criteria.items() if not v]
    total   = len(met)
    risk_label, risk_level = (
        ("Không đủ điều kiện nộp",        "danger")  if total < 3  else
        ("Rủi ro rất cao (RFE ~90%)",      "danger")  if total == 3 else
        ("Rủi ro cao (RFE ~50-60%)",       "warning") if total <= 5 else
        ("Có thể nộp — hồ sơ trung bình", "ok")      if total <= 7 else
        ("Hồ sơ mạnh — nên nộp",          "strong")
    )

    # ── EB-2 NIW prong scoring ────────────────────────────────────────────────
    edu = profile.get("education_history") or []
    degree_rank_map = {"Doctorate (PhD)": 4, "Master's Degree": 3, "Bachelor's Degree": 2}
    highest_rank = max((degree_rank_map.get(e.get("degree_level", ""), 2) for e in edu), default=2)

    all_fields = " ".join(
        [e.get("field_of_study", "") for e in edu] + responsibilities
    ).lower()
    is_stem     = _kw_match([all_fields], _STEM_KW)
    is_strategic = _kw_match([all_fields], _STRAT_KW)
    has_pubs    = bool(pubs)
    has_patents = bool(patents)
    has_awards  = bool(awards)
    exp_months  = _experience_months(profile.get("work_history") or [])
    exp_years   = exp_months / 12

    if is_strategic and has_pubs:       prong1 = 3
    elif is_stem:                        prong1 = 2
    elif has_pubs or has_patents:        prong1 = 1
    else:                                prong1 = 0

    if exp_years > 5 and has_pubs and has_awards and _kw_match(responsibilities, _LEAD_KW):
                                         prong2 = 3
    elif exp_years > 5 and (has_pubs or has_patents): prong2 = 2
    elif exp_years >= 2:                 prong2 = 1
    else:                                prong2 = 0

    is_spec = highest_rank >= 3 or has_pubs or has_patents
    if is_strategic and is_spec:         prong3 = 3
    elif is_spec:                        prong3 = 2
    elif is_stem:                        prong3 = 1
    else:                                prong3 = 0

    niw_total = prong1 + prong2 + prong3
    has_adv = highest_rank >= 3
    base = "Đủ điều kiện cơ bản · " if has_adv else ""
    strength_label, strength_level = (
        (base + "Cần cải thiện nhiều (12+ tháng)", "weak")  if niw_total < 4 else
        (base + "Cần bổ sung gap (6-12 tháng)",   "fair")  if niw_total < 6 else
        (base + "Khả thi cao — nên nộp",           "good")  if niw_total < 8 else
        (base + "Hồ sơ rất mạnh",                  "strong")
    )

    eb1a_ok  = total >= 3
    niw_ok   = niw_total >= 6
    recommended = (
        "Both"   if eb1a_ok and niw_ok else
        "EB-1A"  if eb1a_ok           else
        "EB-2 NIW"
    )

    return {
        "eb1a_criteria_met":     met,
        "eb1a_criteria_missing": missing,
        "eb1a_total_met":        total,
        "eb1a_eligible":         eb1a_ok,
        "eb1a_risk_label":       risk_label,
        "eb1a_risk_level":       risk_level,
        "eb2niw_prong1_score":   prong1,
        "eb2niw_prong2_score":   prong2,
        "eb2niw_prong3_score":   prong3,
        "eb2niw_total_score":    niw_total,
        "eb2niw_eligible":       niw_ok,
        "eb2niw_strength_label": strength_label,
        "eb2niw_strength_level": strength_level,
        "recommended_program":   recommended,
        "experience_months":     exp_months,
    }


def _gap_user_prompt(profile: dict, scores: dict) -> str:
    return f"""## Hồ sơ ứng viên (JSON):
{json.dumps(profile, ensure_ascii=False, indent=2)[:6000]}

## Kết quả chấm điểm:
- EB-1A: {scores["eb1a_total_met"]}/10 tiêu chí → {"ĐỦ ĐIỀU KIỆN" if scores["eb1a_eligible"] else "CHƯA ĐỦ"}
  Đạt: {", ".join(scores["eb1a_criteria_met"]) or "Không có"}
  Chưa đạt: {", ".join(scores["eb1a_criteria_missing"])}

- EB-2 NIW: {scores["eb2niw_total_score"]}/9 điểm → {"ĐỦ ĐIỀU KIỆN" if scores["eb2niw_eligible"] else "CHƯA ĐỦ"}
  Prong 1: {scores["eb2niw_prong1_score"]}/3 | Prong 2: {scores["eb2niw_prong2_score"]}/3 | Prong 3: {scores["eb2niw_prong3_score"]}/3
  Kinh nghiệm: {scores["experience_months"]} tháng

Hãy phân tích và xuất báo cáo gap analysis đầy đủ."""


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_cv(file: UploadFile = File(...)):
    if file.content_type == "application/msword":
        raise HTTPException(400, "Vui lòng convert sang .docx trước khi upload")
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Chỉ chấp nhận PDF hoặc Word (.docx)")

    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(400, "File vượt quá 10 MB")

    t0 = time.time()
    filename = file.filename or "cv.pdf"
    logger.info(f"CV analyze start: {filename} ({len(file_bytes)//1024} KB)")

    # 1. Parse file → text
    markdown = await _parse(file_bytes, filename)
    logger.info(f"Parsed: {len(markdown)} chars")

    # 2. DeepSeek: extract structured profile (JSON mode)
    raw_json = await _deepseek(
        _EXTRACT_SYSTEM,
        f"Extract this CV:\n\n{markdown[:12000]}",
        json_mode=True,
        max_tokens=4096,
        temperature=0.0,
    )
    profile = json.loads(raw_json)
    logger.info(f"Extracted profile: {profile.get('full_name')}")

    # 3. Deterministic scoring (no LLM)
    scores = _score(profile)

    # 4. DeepSeek: gap analysis (markdown report)
    gap_report = await _deepseek(
        _GAP_SYSTEM,
        _gap_user_prompt(profile, scores),
        max_tokens=8192,
        temperature=0.3,
    )
    logger.info(f"Gap analysis done: {len(gap_report)} chars")

    elapsed = round(time.time() - t0, 2)
    logger.info(f"CV analyze done: {filename} in {elapsed}s")

    return {
        "profile": {
            "full_name":       profile.get("full_name", ""),
            "age":             profile.get("age"),
            "current_country": profile.get("current_country"),
            "publications":    profile.get("publications") or [],
            "awards":          profile.get("awards") or [],
            "patents":         profile.get("patents") or [],
            "memberships":     profile.get("memberships") or [],
        },
        "scores":              scores,
        "similar_cases_eb1a":  [],
        "similar_cases_niw":   [],
        "gap_report":          gap_report,
        "drive_folder_url":    "",
        "processing_time_seconds": elapsed,
    }
