from __future__ import annotations

import logging
import time

from fastapi import APIRouter, File, HTTPException, UploadFile

from apps.cv_analyzer.extractor import extract_profile
from apps.cv_analyzer.gap_analyzer import generate_gap_analysis
from apps.cv_analyzer.parser import parse_pdf_to_markdown
from apps.cv_analyzer.schemas import CVAnalysisResponse
from apps.cv_analyzer.scorer import run_scoring

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cv", tags=["CV Analyzer"])

_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/analyze", response_model=CVAnalysisResponse)
async def analyze_cv(file: UploadFile = File(...)):
    """
    Upload CV dạng PDF, nhận về báo cáo Gap Analysis cho EB-1A và EB-2 NIW.

    - Chỉ chấp nhận PDF
    - Giới hạn 10 MB
    - Thời gian xử lý: 20-60 giây tùy độ dài CV
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file PDF")

    pdf_bytes = await file.read()

    if len(pdf_bytes) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File vượt quá 10 MB")

    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="File rỗng")

    logger.info(f"CV analyze request: '{file.filename}' ({len(pdf_bytes)} bytes)")
    start_time = time.perf_counter()

    try:
        # Step 1: PDF → markdown
        markdown = await parse_pdf_to_markdown(pdf_bytes, file.filename or "cv.pdf")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        # Step 2: markdown → ImmigrationProfileSchema (DeepSeek)
        profile = await extract_profile(markdown)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=f"Lỗi trích xuất thông tin CV: {e}")

    # Step 3: Scoring (deterministic Python)
    scores = run_scoring(profile)

    try:
        # Step 4: Gap Analysis (DeepSeek CoT)
        gap_report = await generate_gap_analysis(profile, scores)
    except Exception as e:
        logger.error(f"Gap analysis failed: {e}")
        gap_report = "Không thể tạo báo cáo gap analysis lúc này. Vui lòng thử lại."

    elapsed = round(time.perf_counter() - start_time, 2)
    logger.info(f"CV analyze complete: '{file.filename}' in {elapsed}s")

    return CVAnalysisResponse(
        profile=profile,
        scores=scores,
        gap_report=gap_report,
        processing_time_seconds=elapsed,
    )
