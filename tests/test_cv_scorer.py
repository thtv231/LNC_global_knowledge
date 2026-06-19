from __future__ import annotations
import pytest
from apps.cv_analyzer.schemas import (
    ImmigrationProfileSchema, WorkExperience, EducationInfo,
    DegreeLevel, LanguageProficiency,
)
from apps.cv_analyzer.scorer import (
    calculate_experience_months,
    check_eb1a_criteria,
    score_eb2niw,
)


def _make_profile(**kwargs) -> ImmigrationProfileSchema:
    defaults = dict(
        full_name="Test User",
        education_history=[],
        work_history=[],
        publications=[],
        awards=[],
        memberships=[],
        media_coverage=[],
        patents=[],
        certifications=[],
        speaking_engagements=[],
    )
    defaults.update(kwargs)
    return ImmigrationProfileSchema(**defaults)


def _job(start: str, end: str, full_time: bool = True, title: str = "Engineer") -> WorkExperience:
    return WorkExperience(
        job_title=title,
        company="ACME",
        country="USA",
        start_date=start,
        end_date=end,
        is_full_time=full_time,
        main_responsibilities=["Developed software systems"],
    )


def _edu(level: DegreeLevel, field: str = "Computer Science") -> EducationInfo:
    return EducationInfo(
        degree_level=level,
        field_of_study=field,
        institution="MIT",
        country="USA",
        start_date="2018",
        end_date="2022",
    )


# ── Experience calculation ────────────────────────────────────────────────────

def test_experience_full_time_24_months():
    jobs = [_job("2020-01", "2022-01")]
    assert calculate_experience_months(jobs) == 24


def test_experience_part_time_half_weight():
    jobs = [_job("2020-01", "2022-01", full_time=False)]
    assert calculate_experience_months(jobs) == 12  # 24 months * 0.5


def test_experience_mixed_30_months():
    jobs = [
        _job("2020-01", "2022-01", full_time=True),   # 24 months
        _job("2022-01", "2023-01", full_time=False),  # 12 months * 0.5 = 6
    ]
    assert calculate_experience_months(jobs) == 30


def test_experience_no_overlap():
    jobs = [_job("2020-01", "2021-01"), _job("2021-06", "2022-06")]
    # 12 + 12 = 24 (no overlap)
    assert calculate_experience_months(jobs) == 24


def test_experience_overlapping_jobs_not_double_counted():
    jobs = [_job("2020-01", "2022-01"), _job("2021-01", "2023-01")]
    # Merged: 2020-01 → 2023-01 = 36 months
    assert calculate_experience_months(jobs) == 36


# ── EB-1A criteria ────────────────────────────────────────────────────────────

def test_eb1a_eligible_with_3_criteria():
    profile = _make_profile(
        awards=["Best Paper Award, CVPR, 2023"],
        publications=["Paper A, Nature, 2022"],
        memberships=["IEEE Senior Member"],
    )
    result = check_eb1a_criteria(profile)
    assert result["eligible"] is True
    assert result["total_met"] >= 3


def test_eb1a_not_eligible_with_2_criteria():
    # awards → 1 criterion, memberships → 1 criterion (publications absent → no overlap)
    profile = _make_profile(
        awards=["Best Paper Award, CVPR, 2023"],
        memberships=["IEEE Member"],
    )
    result = check_eb1a_criteria(profile)
    assert result["eligible"] is False
    assert result["total_met"] == 2


def test_eb1a_judge_keyword_detected():
    profile = _make_profile(
        work_history=[
            WorkExperience(
                job_title="Researcher",
                company="Lab",
                country="USA",
                start_date="2020-01",
                end_date="Present",
                is_full_time=True,
                main_responsibilities=["Served as peer reviewer for NeurIPS"],
            )
        ],
        publications=["Paper A, ICML 2022"],
        awards=["NSF Fellowship"],
    )
    result = check_eb1a_criteria(profile)
    assert "Đánh giá công trình người khác (Judge/Reviewer)" in result["criteria_met"]
    assert result["eligible"] is True


def test_eb1a_leadership_detected():
    profile = _make_profile(
        work_history=[_job("2018-01", "Present", title="Director of Engineering")],
        publications=["Paper"],
        awards=["Award"],
    )
    result = check_eb1a_criteria(profile)
    assert "Vai trò lãnh đạo/Critical trong tổ chức uy tín" in result["criteria_met"]


# ── EB-2 NIW scoring ──────────────────────────────────────────────────────────

def test_eb2niw_stem_phd_eligible():
    profile = _make_profile(
        education_history=[_edu(DegreeLevel.PHD, "Artificial Intelligence")],
        work_history=[_job("2018-01", "Present")],
        publications=["Paper A", "Paper B", "Paper C"],
        awards=["Best Researcher Award 2023"],
    )
    exp_months = calculate_experience_months(profile.work_history)
    result = score_eb2niw(profile, exp_months)
    assert result["total"] >= 6
    assert result["eligible"] is True


def test_eb2niw_insufficient_bachelor_no_pub():
    profile = _make_profile(
        education_history=[_edu(DegreeLevel.BACHELORS, "Business Administration")],
        work_history=[_job("2022-01", "2024-01")],
    )
    exp_months = calculate_experience_months(profile.work_history)
    result = score_eb2niw(profile, exp_months)
    assert result["total"] < 6
    assert result["eligible"] is False


def test_eb2niw_prong1_strategic_field():
    profile = _make_profile(
        education_history=[_edu(DegreeLevel.MASTERS, "Machine Learning")],
        work_history=[_job("2019-01", "Present")],
        publications=["Deep Learning Paper, NeurIPS 2023"],
    )
    exp_months = calculate_experience_months(profile.work_history)
    result = score_eb2niw(profile, exp_months)
    assert result["prong1"] == 3  # strategic field + publications


def test_eb2niw_prong2_above_5_years_with_pub():
    profile = _make_profile(
        education_history=[_edu(DegreeLevel.PHD, "Physics")],
        work_history=[_job("2018-01", "Present")],
        publications=["Quantum Paper 2021"],
    )
    exp_months = calculate_experience_months(profile.work_history)
    assert exp_months > 60
    result = score_eb2niw(profile, exp_months)
    assert result["prong2"] >= 2
