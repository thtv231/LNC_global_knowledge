from __future__ import annotations
import asyncio
import time
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from apps.cv_analyzer.parser import parse_cv_to_markdown
from apps.cv_analyzer.extractor import extract_profile
from apps.cv_analyzer.scorer import calculate_experience_months, check_eb1a_criteria, score_eb2niw, get_eb1a_risk, get_eb2niw_strength
from apps.cv_analyzer.schemas import DegreeLevel
from apps.cv_analyzer.gap_analyzer import generate_gap_analysis
from apps.cv_analyzer.case_matcher import find_similar_cases
from apps.cv_analyzer.drive_storage import save_cv_to_drive
from apps.cv_analyzer.schemas import CVAnalysisResponse, USAScoreResult
from dataclasses import asdict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cv", tags=["CV Analyzer"])

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("/analyze", response_model=CVAnalysisResponse)
async def analyze_cv(file: UploadFile = File(...)):
    """
    Upload CV (PDF hoặc .docx), nhận báo cáo Gap Analysis cho EB-1A và EB-2 NIW.
    Thời gian xử lý: 15-60 giây.
    """
    if file.content_type == "application/msword":
        raise HTTPException(400, "Vui lòng convert sang .docx trước khi upload")
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, "Chỉ chấp nhận PDF hoặc Word (.docx)")

    file_bytes = await file.read()

    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(400, "File vượt quá 10MB")

    start_time = time.time()
    logger.info(f"CV analyze start: {file.filename} ({len(file_bytes)//1024}KB)")

    # Step 1: Parse file → Markdown
    markdown = await parse_cv_to_markdown(file_bytes, file.filename or "cv.pdf")

    # Step 2: Groq extraction → ImmigrationProfileSchema
    profile = await extract_profile(markdown)

    # Step 3: Deterministic scoring
    exp_months = calculate_experience_months(profile.work_history)
    eb1a_result = check_eb1a_criteria(profile)
    eb2niw_result = score_eb2niw(profile, exp_months)

    recommended = "Both" if (eb1a_result["eligible"] and eb2niw_result["eligible"]) \
        else ("EB-1A" if eb1a_result["eligible"] else "EB-2 NIW")

    eb1a_risk_label, eb1a_risk_level = get_eb1a_risk(eb1a_result["total_met"])

    _advanced_degrees = {DegreeLevel.PHD, DegreeLevel.MASTERS, DegreeLevel.POST_GRAD}
    has_advanced = any(e.degree_level in _advanced_degrees for e in profile.education_history)
    # Medical degrees (Bác sĩ, MD, specialist) = advanced degree for EB-2 NIW purposes
    _medical_keywords = {"bác sĩ", "specialist", "physician", "doctor", "md", "mbbs", "chuyên khoa"}
    if not has_advanced:
        all_edu_text = " ".join(
            f"{e.field_of_study} {e.degree_level.value}".lower()
            for e in profile.education_history
        )
        has_advanced = any(k in all_edu_text for k in _medical_keywords)

    eb2niw_strength_label, eb2niw_strength_level = get_eb2niw_strength(
        eb2niw_result["total"], has_advanced
    )

    scores = USAScoreResult(
        eb1a_criteria_met=eb1a_result["criteria_met"],
        eb1a_criteria_missing=eb1a_result["criteria_missing"],
        eb1a_total_met=eb1a_result["total_met"],
        eb1a_eligible=eb1a_result["eligible"],
        eb1a_risk_label=eb1a_risk_label,
        eb1a_risk_level=eb1a_risk_level,
        eb2niw_prong1_score=eb2niw_result["prong1"],
        eb2niw_prong2_score=eb2niw_result["prong2"],
        eb2niw_prong3_score=eb2niw_result["prong3"],
        eb2niw_total_score=eb2niw_result["total"],
        eb2niw_eligible=eb2niw_result["eligible"],
        eb2niw_strength_label=eb2niw_strength_label,
        eb2niw_strength_level=eb2niw_strength_level,
        recommended_program=recommended,
        experience_months=exp_months,
    )

    # Step 3b: Similar cases từ database thực tế
    similar_eb1a = find_similar_cases(profile, scores, "EB-1A", top_k=5)
    similar_niw = find_similar_cases(profile, scores, "EB-2 NIW", top_k=5)

    # Step 4: DeepSeek gap analysis
    gap_report = await generate_gap_analysis(profile, scores, similar_eb1a + similar_niw)

    elapsed = round(time.time() - start_time, 2)
    logger.info(f"CV analyze done: {file.filename} in {elapsed}s")

    # Step 5: Fire-and-forget Drive upload — does not block response
    asyncio.create_task(
        save_cv_to_drive(
            file_bytes=file_bytes,
            original_filename=file.filename or "cv.pdf",
            profile_json=profile.model_dump_json(indent=2),
            scores_json=scores.model_dump_json(indent=2),
            gap_report=gap_report,
        )
    )

    return CVAnalysisResponse(
        profile=profile,
        scores=scores,
        similar_cases_eb1a=[asdict(c) for c in similar_eb1a],
        similar_cases_niw=[asdict(c) for c in similar_niw],
        gap_report=gap_report,
        drive_folder_url="",
        processing_time_seconds=elapsed,
    )
