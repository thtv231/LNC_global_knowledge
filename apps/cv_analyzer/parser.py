from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import fitz  # pymupdf

logger = logging.getLogger(__name__)

_MIN_CHARS = 200


def _parse_pdf_sync(pdf_bytes: bytes, filename: str) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: list[str] = []
    try:
        for page in doc:
            try:
                # get_text("markdown") requires pymupdf >= 1.24
                text = page.get_text("markdown")
            except Exception:
                text = page.get_text("text")
            if text.strip():
                pages.append(text.strip())
    finally:
        doc.close()

    result = "\n\n".join(pages)

    if len(result) < _MIN_CHARS:
        raise ValueError(f"PDF quá ngắn hoặc không đọc được text: {filename} ({len(result)} ký tự)")

    logger.info(f"Parser used: PyMuPDF for '{filename}' — {len(result)} chars, {len(pages)} pages")
    return result


async def parse_pdf_to_markdown(pdf_bytes: bytes, filename: str) -> str:
    """
    Parse PDF bytes sang markdown text.
    Chạy trong thread pool để không block event loop.
    Raises ValueError nếu kết quả rỗng/quá ngắn.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _parse_pdf_sync, pdf_bytes, filename)
