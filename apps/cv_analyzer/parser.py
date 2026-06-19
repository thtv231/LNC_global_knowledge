from __future__ import annotations
import asyncio
import logging
from io import BytesIO
from pathlib import Path

logger = logging.getLogger(__name__)


def _parse_with_pymupdf(pdf_bytes: bytes) -> str:
    import pymupdf  # fitz
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    parts = []
    for page in doc:
        parts.append(page.get_text("text"))
    doc.close()
    return "\n\n".join(parts)


def _parse_with_marker(pdf_bytes: bytes, filename: str) -> str:
    from marker.convert import convert_single_pdf
    from marker.models import load_all_models
    models = load_all_models()
    full_text, _, _ = convert_single_pdf(pdf_bytes, models)
    return full_text


async def _parse_with_llamaparse(pdf_bytes: bytes, filename: str) -> str:
    import os, httpx, asyncio, time
    api_key = os.getenv("LLAMA_CLOUD_API_KEY", "")
    if not api_key:
        raise ValueError("LLAMA_CLOUD_API_KEY not set")

    async with httpx.AsyncClient(timeout=90) as client:
        upload_resp = await client.post(
            "https://api.cloud.llamaindex.ai/api/parsing/upload",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename, pdf_bytes, "application/pdf")},
            data={"result_type": "markdown"},
        )
        upload_resp.raise_for_status()
        job_id = upload_resp.json()["id"]

        deadline = asyncio.get_event_loop().time() + 60
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(3)
            status_resp = await client.get(
                f"https://api.cloud.llamaindex.ai/api/parsing/job/{job_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            status = status_resp.json().get("status")
            if status == "SUCCESS":
                result_resp = await client.get(
                    f"https://api.cloud.llamaindex.ai/api/parsing/job/{job_id}/result/markdown",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                return result_resp.json().get("markdown", "")
            if status in ("ERROR", "CANCELLED"):
                raise ValueError(f"LlamaParse job failed: {status}")

        raise TimeoutError("LlamaParse timeout after 60s")


async def parse_pdf_to_markdown(pdf_bytes: bytes, filename: str) -> str:
    loop = asyncio.get_event_loop()

    # Primary: pymupdf (no install required — already available)
    try:
        text = await loop.run_in_executor(None, _parse_with_pymupdf, pdf_bytes)
        if len(text) >= 200:
            logger.info(f"Parser used: pymupdf for {filename}")
            return text
        logger.warning(f"pymupdf output too short ({len(text)} chars), trying marker...")
    except Exception as e:
        logger.warning(f"pymupdf failed for {filename}: {e}")

    # Secondary: Marker (if installed)
    try:
        text = await loop.run_in_executor(None, _parse_with_marker, pdf_bytes, filename)
        if len(text) >= 200:
            logger.info(f"Parser used: marker for {filename}")
            return text
    except Exception as e:
        logger.warning(f"Marker failed for {filename}: {e}")

    # Fallback: LlamaParse (requires LLAMA_CLOUD_API_KEY)
    import os
    if os.getenv("LLAMA_CLOUD_API_KEY"):
        text = await _parse_with_llamaparse(pdf_bytes, filename)
        logger.info(f"Parser used: llamaparse for {filename}")
        return text

    raise ValueError(f"Không thể parse PDF '{filename}'. Thử upload lại hoặc convert sang DOCX.")


def _docx_to_markdown(docx_bytes: bytes) -> str:
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


async def parse_cv_to_markdown(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".docx":
        loop = asyncio.get_event_loop()
        markdown = await loop.run_in_executor(None, _docx_to_markdown, file_bytes)
        logger.info(f"Parser used: python-docx for {filename}")
        return markdown
    elif ext == ".pdf":
        return await parse_pdf_to_markdown(file_bytes, filename)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Chỉ chấp nhận PDF hoặc DOCX.")
