from __future__ import annotations
import os
import json
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

CASES_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "curated", "cases.json")

_DEGREE_RANK = {
    "ph.d.": 4, "phd": 4, "doctorate": 4, "d.sc.": 4,
    "master's": 3, "masters": 3, "m.s.": 3, "m.sc.": 3, "m.eng.": 3,
    "bachelor's": 2, "bachelors": 2, "b.s.": 2, "b.sc.": 2, "b.eng.": 2,
    "high school": 1,
}

_PROGRAM_ALIASES = {
    "eb2-niw": "EB-2 NIW",
    "eb-2 niw": "EB-2 NIW",
    "eb2 niw": "EB-2 NIW",
    "niw": "EB-2 NIW",
    "eb-1a": "EB-1A",
    "eb1a": "EB-1A",
    "eb1-a": "EB-1A",
}


def _normalize_program(raw: str) -> str:
    return _PROGRAM_ALIASES.get(raw.strip().lower(), raw.strip())


def _degree_rank(degree_str: str) -> int:
    if not degree_str:
        return 2
    d = degree_str.lower()
    for key, rank in _DEGREE_RANK.items():
        if key in d:
            return rank
    return 2


@lru_cache(maxsize=1)
def load_cases() -> list[dict]:
    with open(CASES_JSON_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    cases = []
    for item in raw:
        program_raw = item.get("program", "") or ""
        program = _normalize_program(program_raw)
        if program not in ("EB-1A", "EB-2 NIW"):
            continue

        pub = item.get("publications")
        cit = item.get("citations")
        letters = item.get("recommendation_letters") or item.get("testimonial_letters")
        deg = item.get("degree", "") or ""

        cases.append({
            "program": program,
            "field": item.get("field", "") or "",
            "degree": deg,
            "degree_rank": _degree_rank(deg),
            "current_role": item.get("current_role", "") or "",
            "publications": float(pub) if pub is not None else 0.0,
            "citations": float(cit) if cit is not None else 0.0,
            "recommendation_letters": float(letters) if letters is not None else 0.0,
            "post_rfe": bool(item.get("post_rfe", False)),
            "approval_date": str(item.get("approval_date", "") or ""),
            "processing_days": float(item.get("processing_days") or 0),
            "premium_processing": str(item.get("premium_processing") or "standard"),
            "notable": str(item.get("notable", "") or ""),
            "source_url": str(item.get("source_url", "") or ""),
        })

    logger.info(f"Loaded {len(cases)} approved cases from {CASES_JSON_PATH}")
    return cases


def get_cases_by_program(program: str) -> list[dict]:
    all_cases = load_cases()
    norm = _normalize_program(program)
    return [c for c in all_cases if c["program"] == norm]
