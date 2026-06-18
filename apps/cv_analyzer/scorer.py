from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Tuple

from apps.cv_analyzer.schemas import (
    ImmigrationProfileSchema,
    USAScoreResult,
    WorkExperience,
)

# ---------------------------------------------------------------------------
# Keyword sets cho các criteria định tính
# ---------------------------------------------------------------------------

_LEADERSHIP_KW = {
    "lead", "leader", "head", "director", "manager", "chief", "vp",
    "vice president", "president", "founder", "co-founder", "principal",
    "senior", "staff engineer", "principal engineer", "technical lead",
    "team lead", "dept head", "department head",
}

_JUDGE_KW = {
    "reviewer", "review", "judge", "referee", "editorial board",
    "peer review", "committee", "panel", "advisory board", "program committee",
    "technical committee",
}

_ART_KW = {
    "exhibition", "exhibit", "gallery", "performance", "concert",
    "recital", "art show", "festival", "showcase", "artwork",
}

_HIGH_SALARY_KW = {
    "high salary", "competitive salary", "above average", "equity",
    "stock option", "top percentile", "significantly higher",
}

_STEM_KW = {
    "engineering", "computer science", "software", "ai", "artificial intelligence",
    "machine learning", "deep learning", "biology", "chemistry", "physics",
    "medicine", "healthcare", "medical", "data science", "cybersecurity",
    "biotechnology", "neuroscience", "mathematics", "statistics",
    "environmental", "energy", "defense", "semiconductor", "quantum",
    "electrical", "mechanical", "civil", "aerospace",
}

_STRATEGIC_KW = {
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "biotech", "biotechnology", "energy", "defense", "national security",
    "semiconductor", "quantum computing", "generative ai",
}


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> date:
    s = s.strip()
    if s.lower() in {"present", "now", "current", "hiện tại", "nay"}:
        return date.today()
    for fmt in ("%Y-%m", "%Y-%m-%d", "%m/%Y", "%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return date.today()


def _months_between(start: date, end: date) -> int:
    if end < start:
        return 0
    return (end.year - start.year) * 12 + (end.month - start.month)


def _merge_intervals(intervals: List[Tuple[date, date]]) -> List[Tuple[date, date]]:
    if not intervals:
        return []
    sorted_iv = sorted(intervals, key=lambda x: x[0])
    merged = [list(sorted_iv[0])]
    for start, end in sorted_iv[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [tuple(iv) for iv in merged]  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Experience calculation
# ---------------------------------------------------------------------------

def calculate_experience_months(work_history: List[WorkExperience]) -> int:
    """
    Tổng tháng kinh nghiệm: full-time merge intervals, part-time tính 0.5x.
    """
    full_time: List[Tuple[date, date]] = []
    part_time_months = 0

    for job in work_history:
        try:
            start = _parse_date(job.start_date)
            end = _parse_date(job.end_date)
        except Exception:
            continue

        if job.is_full_time:
            full_time.append((start, end))
        else:
            part_time_months += _months_between(start, end) // 2  # 0.5x

    merged = _merge_intervals(full_time)
    full_time_months = sum(_months_between(s, e) for s, e in merged)

    return full_time_months + part_time_months


# ---------------------------------------------------------------------------
# Keyword helpers
# ---------------------------------------------------------------------------

def _text_has_kw(texts: List[str], keywords: set) -> bool:
    combined = " ".join(texts).lower()
    return any(kw in combined for kw in keywords)


def _profile_field_text(profile: ImmigrationProfileSchema) -> str:
    return " ".join(
        e.field_of_study.lower() for e in profile.education_history
    ) + " " + " ".join(
        j.job_title.lower() for j in profile.work_history
    )


# ---------------------------------------------------------------------------
# EB-1A — 10 criteria
# ---------------------------------------------------------------------------

def check_eb1a_criteria(profile: ImmigrationProfileSchema) -> Dict:
    all_titles = [j.job_title for j in profile.work_history]
    all_resp: List[str] = []
    for j in profile.work_history:
        all_resp.extend(j.main_responsibilities)

    criteria: Dict[str, bool] = {
        "Awards & Prizes": bool(profile.awards),
        "Professional Memberships": bool(profile.memberships),
        "Media Coverage": bool(profile.media_coverage),
        "Judge/Reviewer Role": _text_has_kw(all_titles + all_resp, _JUDGE_KW),
        "Original Contributions": bool(profile.publications or profile.patents),
        "Scholarly Articles": bool(profile.publications),
        "Artistic Exhibitions": _text_has_kw(all_titles + all_resp, _ART_KW),
        "Leading/Critical Role": _text_has_kw(all_titles + all_resp, _LEADERSHIP_KW),
        "High Salary": _text_has_kw(all_resp, _HIGH_SALARY_KW),
        "Commercial Success in Arts": False,  # hiếm, cần bằng chứng doanh thu
    }

    met = [name for name, val in criteria.items() if val]
    missing = [name for name, val in criteria.items() if not val]

    return {
        "criteria_met": met,
        "criteria_missing": missing,
        "total_met": len(met),
        "eligible": len(met) >= 3,
    }


# ---------------------------------------------------------------------------
# EB-2 NIW — 3 prong scoring
# ---------------------------------------------------------------------------

def score_eb2niw(profile: ImmigrationProfileSchema, exp_months: int) -> Dict:
    field_text = _profile_field_text(profile)
    is_stem = any(kw in field_text for kw in _STEM_KW)
    is_strategic = any(kw in field_text for kw in _STRATEGIC_KW)

    exp_years = exp_months / 12
    has_pubs = bool(profile.publications)
    has_patents = bool(profile.patents)
    has_awards = bool(profile.awards)
    has_speaking = bool(profile.speaking_engagements)

    all_titles = [j.job_title for j in profile.work_history]
    all_resp: List[str] = []
    for j in profile.work_history:
        all_resp.extend(j.main_responsibilities)
    is_leader = _text_has_kw(all_titles + all_resp, _LEADERSHIP_KW)

    # Prong 1 — Substantial Merit & National Importance (0-3)
    if is_strategic and has_pubs:
        prong1 = 3
    elif is_stem:
        prong1 = 2
    elif profile.education_history:
        prong1 = 1
    else:
        prong1 = 0

    # Prong 2 — Well Positioned to Advance (0-3)
    if exp_years >= 5 and has_pubs and has_awards and is_leader:
        prong2 = 3
    elif exp_years >= 5 and (has_pubs or has_patents):
        prong2 = 2
    elif exp_years >= 2:
        prong2 = 1
    else:
        prong2 = 0

    # Prong 3 — Beneficial to US to Waive Job Offer (0-3)
    if is_strategic and (has_pubs or has_patents) and exp_years >= 5:
        prong3 = 3
    elif is_stem and exp_years >= 3:
        prong3 = 2
    elif is_stem or has_speaking:
        prong3 = 1
    else:
        prong3 = 0

    total = prong1 + prong2 + prong3

    return {
        "prong1": prong1,
        "prong2": prong2,
        "prong3": prong3,
        "total": total,
        "eligible": total >= 6,
    }


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def run_scoring(profile: ImmigrationProfileSchema) -> USAScoreResult:
    exp_months = calculate_experience_months(profile.work_history)
    eb1a = check_eb1a_criteria(profile)
    niw = score_eb2niw(profile, exp_months)

    both_eligible = eb1a["eligible"] and niw["eligible"]
    if both_eligible:
        recommended = "Both"
    elif eb1a["eligible"]:
        recommended = "EB-1A"
    else:
        recommended = "EB-2 NIW"

    return USAScoreResult(
        eb1a_criteria_met=eb1a["criteria_met"],
        eb1a_criteria_missing=eb1a["criteria_missing"],
        eb1a_total_met=eb1a["total_met"],
        eb1a_eligible=eb1a["eligible"],
        eb2niw_prong1_score=niw["prong1"],
        eb2niw_prong2_score=niw["prong2"],
        eb2niw_prong3_score=niw["prong3"],
        eb2niw_total_score=niw["total"],
        eb2niw_eligible=niw["eligible"],
        recommended_program=recommended,
        experience_months=exp_months,
    )
