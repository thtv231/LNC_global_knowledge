from __future__ import annotations
from datetime import date
from typing import List
from apps.cv_analyzer.schemas import ImmigrationProfileSchema, WorkExperience

_LEADERSHIP_KEYWORDS = {
    "director", "head", "lead", "principal", "chief", "vp", "president",
    "founder", "co-founder", "manager", "supervisor", "chair", "dean",
    "trưởng", "giám đốc", "phó", "trưởng nhóm",
}

_JUDGE_KEYWORDS = {
    "reviewer", "review", "judge", "peer review", "editorial board",
    "program committee", "phản biện", "đánh giá",
}

_ART_KEYWORDS = {
    "exhibition", "gallery", "exhibit", "display", "showcase",
    "triển lãm", "gallery", "nghệ thuật",
}

_SALARY_KEYWORDS = {
    "salary", "compensation", "bonus", "high earning", "top percentile",
    "lương cao", "thu nhập",
}

_STEM_FIELDS = {
    "computer", "software", "engineering", "physics", "chemistry",
    "biology", "biotech", "mathematics", "data", "artificial intelligence",
    "machine learning", "neuroscience", "medicine", "healthcare",
    "energy", "defense", "aerospace", "robotics", "genomics",
}

_STRATEGIC_FIELDS = {
    "artificial intelligence", "ai", "machine learning", "biotech",
    "biotechnology", "energy", "defense", "aerospace", "genomics",
    "quantum", "cybersecurity",
}


def _months_between(start: str, end: str) -> int:
    """Parse YYYY-MM strings (or YYYY). Returns months difference."""
    def parse(s: str):
        s = s.strip()
        if s.lower() == "present":
            return date.today()
        parts = s.split("-")
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        return date(year, month, 1)

    try:
        s = parse(start)
        e = parse(end)
        if e < s:
            return 0
        return (e.year - s.year) * 12 + (e.month - s.month)
    except Exception:
        return 0


def _merge_intervals(intervals: list[tuple[date, date]]) -> list[tuple[date, date]]:
    """Merge overlapping date intervals."""
    if not intervals:
        return []
    sorted_iv = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_iv[0]]
    for start, end in sorted_iv[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def calculate_experience_months(work_history: list[WorkExperience]) -> int:
    def parse_date(s: str) -> date:
        s = s.strip()
        if s.lower() == "present":
            return date.today()
        parts = s.split("-")
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        return date(year, month, 1)

    full_intervals = []
    part_intervals = []

    for job in work_history:
        try:
            s = parse_date(job.start_date)
            e = parse_date(job.end_date)
            if e < s:
                continue
            if job.is_full_time:
                full_intervals.append((s, e))
            else:
                part_intervals.append((s, e))
        except Exception:
            continue

    def intervals_to_months(intervals):
        merged = _merge_intervals(intervals)
        total = 0
        for s, e in merged:
            total += (e.year - s.year) * 12 + (e.month - s.month)
        return total

    full_months = intervals_to_months(full_intervals)
    part_months = intervals_to_months(part_intervals) // 2
    return full_months + part_months


def _has_keywords(texts: list[str], keywords: set[str]) -> bool:
    combined = " ".join(texts).lower()
    return any(k in combined for k in keywords)


def _all_responsibilities(profile: ImmigrationProfileSchema) -> list[str]:
    result = []
    for job in profile.work_history:
        result.extend(job.main_responsibilities)
        result.append(job.job_title)
    return result


def check_eb1a_criteria(profile: ImmigrationProfileSchema) -> dict:
    responsibilities = _all_responsibilities(profile)

    criteria = {
        "Awards/Prizes xuất sắc": bool(profile.awards),
        "Membership hội nghề nghiệp uy tín": bool(profile.memberships),
        "Media coverage về công việc": bool(profile.media_coverage),
        "Đánh giá công trình người khác (Judge/Reviewer)": _has_keywords(responsibilities, _JUDGE_KEYWORDS),
        "Original contributions (Publications/Patents)": bool(profile.publications) or bool(profile.patents),
        "Bài báo khoa học trong journal/conference": bool(profile.publications),
        "Triển lãm tác phẩm nghệ thuật": _has_keywords(responsibilities, _ART_KEYWORDS),
        "Vai trò lãnh đạo/Critical trong tổ chức uy tín": _has_keywords(responsibilities, _LEADERSHIP_KEYWORDS),
        "Mức lương cao hơn peers (High Salary)": _has_keywords(responsibilities, _SALARY_KEYWORDS),
        "Thành công thương mại trong nghệ thuật": False,
    }

    met = [name for name, val in criteria.items() if val]
    missing = [name for name, val in criteria.items() if not val]

    return {
        "criteria_met": met,
        "criteria_missing": missing,
        "total_met": len(met),
        "eligible": len(met) >= 3,
    }


def score_eb2niw(profile: ImmigrationProfileSchema, exp_months: int) -> dict:
    responsibilities = _all_responsibilities(profile)
    all_text = " ".join(responsibilities).lower()

    # Education
    degree_rank = {
        "Doctorate (PhD)": 4,
        "Master's Degree": 3,
        "Post-Graduate Diploma/Certificate": 3,
        "Bachelor's Degree": 2,
        "Two-Year College/Technical Diploma": 1,
        "High School Graduation": 1,
        "Other/Unspecified": 2,
    }
    highest_rank = max(
        (degree_rank.get(e.degree_level.value, 2) for e in profile.education_history),
        default=2,
    )

    # Field detection
    all_fields = " ".join(
        [e.field_of_study for e in profile.education_history] + responsibilities
    ).lower()
    is_stem = any(f in all_fields for f in _STEM_FIELDS)
    is_strategic = any(f in all_fields for f in _STRATEGIC_FIELDS)

    has_publications = bool(profile.publications)
    has_patents = bool(profile.patents)
    has_awards = bool(profile.awards)
    exp_years = exp_months / 12

    # Prong 1: Substantial Merit & National Importance
    if is_strategic and has_publications:
        prong1 = 3
    elif is_stem:
        prong1 = 2
    elif has_publications or has_patents:
        prong1 = 1
    else:
        prong1 = 0

    # Prong 2: Well Positioned to Advance
    if exp_years > 5 and has_publications and has_awards and _has_keywords(responsibilities, _LEADERSHIP_KEYWORDS):
        prong2 = 3
    elif exp_years > 5 and (has_publications or has_patents):
        prong2 = 2
    elif exp_years >= 2:
        prong2 = 1
    else:
        prong2 = 0

    # Prong 3: Beneficial to US to Waive
    is_specialized = highest_rank >= 3 or has_publications or has_patents
    if is_strategic and is_specialized:
        prong3 = 3
    elif is_specialized:
        prong3 = 2
    elif is_stem:
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


def get_eb1a_risk(total_met: int) -> tuple[str, str]:
    """Returns (label, level) where level is danger/warning/ok/strong."""
    if total_met < 3:
        return "Không đủ điều kiện nộp", "danger"
    elif total_met == 3:
        return "Rủi ro rất cao (RFE ~90%)", "danger"
    elif total_met <= 5:
        return "Rủi ro cao (RFE ~50-60%)", "warning"
    elif total_met <= 7:
        return "Có thể nộp — hồ sơ trung bình", "ok"
    else:
        return "Hồ sơ mạnh — nên nộp", "strong"


def get_eb2niw_strength(total_score: int, has_advanced_degree: bool) -> tuple[str, str]:
    """
    EB-2 NIW: Advanced Degree holders (MD, specialist, Master's, PhD) are always
    eligible to APPLY. Score reflects APPLICATION STRENGTH, not eligibility.
    Returns (label, level) where level is weak/fair/good/strong.
    """
    base = "Đủ điều kiện cơ bản · " if has_advanced_degree else ""
    if total_score < 4:
        return base + "Cần cải thiện nhiều (12+ tháng)", "weak"
    elif total_score < 6:
        return base + "Cần bổ sung gap (6-12 tháng)", "fair"
    elif total_score < 8:
        return base + "Khả thi cao — nên nộp", "good"
    else:
        return base + "Hồ sơ rất mạnh", "strong"
