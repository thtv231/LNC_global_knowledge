"""Unit tests cho CV scorer (deterministic, không cần LLM)."""
from __future__ import annotations

import pytest

from apps.cv_analyzer.schemas import (
    DegreeLevel,
    EducationInfo,
    ImmigrationProfileSchema,
    WorkExperience,
)
from apps.cv_analyzer.scorer import (
    calculate_experience_months,
    check_eb1a_criteria,
    run_scoring,
    score_eb2niw,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_profile(**kwargs) -> ImmigrationProfileSchema:
    defaults = dict(
        full_name="Test User",
        education_history=[
            EducationInfo(
                degree_level=DegreeLevel.PHD,
                field_of_study="Computer Science",
                institution="MIT",
                country="USA",
                start_date="2015-09",
                end_date="2020-05",
            )
        ],
        work_history=[],
    )
    defaults.update(kwargs)
    return ImmigrationProfileSchema(**defaults)


def _make_job(start: str, end: str, title: str = "Engineer", full_time: bool = True,
              responsibilities: list[str] | None = None) -> WorkExperience:
    return WorkExperience(
        job_title=title,
        company="Corp",
        country="USA",
        start_date=start,
        end_date=end,
        is_full_time=full_time,
        main_responsibilities=responsibilities or ["Developed software systems"],
    )


# ---------------------------------------------------------------------------
# calculate_experience_months
# ---------------------------------------------------------------------------

class TestExperienceMonths:
    def test_single_full_time_24_months(self):
        jobs = [_make_job("2020-01", "2022-01")]
        assert calculate_experience_months(jobs) == 24

    def test_part_time_counted_half(self):
        # 12 months part-time → 6
        jobs = [_make_job("2021-01", "2022-01", full_time=False)]
        assert calculate_experience_months(jobs) == 6

    def test_overlapping_intervals_not_double_counted(self):
        # Two overlapping jobs: 2020-01 → 2022-01 AND 2021-01 → 2023-01
        # Merged: 2020-01 → 2023-01 = 36 months
        jobs = [
            _make_job("2020-01", "2022-01"),
            _make_job("2021-01", "2023-01"),
        ]
        assert calculate_experience_months(jobs) == 36

    def test_non_overlapping_jobs_summed(self):
        # 12 months + 12 months = 24
        jobs = [
            _make_job("2020-01", "2021-01"),
            _make_job("2022-01", "2023-01"),
        ]
        assert calculate_experience_months(jobs) == 24

    def test_mixed_full_and_part_time(self):
        # Full-time: 24 months, Part-time: 12 months → 0.5x = 6 → total 30
        jobs = [
            _make_job("2020-01", "2022-01", full_time=True),
            _make_job("2022-01", "2023-01", full_time=False),
        ]
        assert calculate_experience_months(jobs) == 30

    def test_empty_work_history(self):
        assert calculate_experience_months([]) == 0


# ---------------------------------------------------------------------------
# check_eb1a_criteria
# ---------------------------------------------------------------------------

class TestEB1ACriteria:
    def test_eligible_with_3_criteria(self):
        profile = _make_profile(
            awards=["Best Paper Award 2022"],
            publications=["Nature 2022 - Deep Learning in Genomics"],
            memberships=["ACM Senior Member"],
        )
        result = check_eb1a_criteria(profile)
        assert result["eligible"] is True
        assert result["total_met"] >= 3
        assert "Awards & Prizes" in result["criteria_met"]
        assert "Scholarly Articles" in result["criteria_met"]
        assert "Professional Memberships" in result["criteria_met"]

    def test_not_eligible_with_only_awards(self):
        # Chỉ có awards → 1 criteria → không đủ điều kiện
        profile = _make_profile(awards=["Best Paper Award"])
        result = check_eb1a_criteria(profile)
        assert result["total_met"] == 1
        assert result["eligible"] is False

    def test_publications_counts_as_two_criteria(self):
        # publications kích hoạt cả "Original Contributions" lẫn "Scholarly Articles"
        profile = _make_profile(publications=["Journal 2022"])
        result = check_eb1a_criteria(profile)
        assert "Original Contributions" in result["criteria_met"]
        assert "Scholarly Articles" in result["criteria_met"]

    def test_leadership_keyword_detected(self):
        profile = _make_profile(
            work_history=[_make_job("2020-01", "Present", title="Engineering Director")],
        )
        result = check_eb1a_criteria(profile)
        assert "Leading/Critical Role" in result["criteria_met"]

    def test_judge_keyword_in_responsibilities(self):
        profile = _make_profile(
            work_history=[_make_job(
                "2020-01", "Present",
                responsibilities=["Served as peer reviewer for IEEE journal"],
            )],
        )
        result = check_eb1a_criteria(profile)
        assert "Judge/Reviewer Role" in result["criteria_met"]

    def test_no_criteria_empty_profile(self):
        profile = _make_profile()
        result = check_eb1a_criteria(profile)
        assert result["eligible"] is False
        assert result["total_met"] == 0


# ---------------------------------------------------------------------------
# score_eb2niw
# ---------------------------------------------------------------------------

class TestEB2NIW:
    def test_stem_phd_with_publications_eligible(self):
        profile = _make_profile(
            publications=["IEEE Trans. 2021", "NeurIPS 2022"],
            awards=["NSF Grant Recipient"],
            work_history=[
                _make_job("2018-01", "Present", title="AI Research Scientist",
                          responsibilities=["Led deep learning research projects"]),
            ],
        )
        exp_months = calculate_experience_months(profile.work_history)
        result = score_eb2niw(profile, exp_months)
        assert result["total"] >= 6
        assert result["eligible"] is True

    def test_insufficient_no_pubs_short_exp(self):
        profile = _make_profile(
            education_history=[
                EducationInfo(
                    degree_level=DegreeLevel.BACHELORS,
                    field_of_study="Business Administration",
                    institution="State College",
                    country="Vietnam",
                )
            ],
            work_history=[_make_job("2023-01", "2025-01", title="Sales Manager")],
        )
        exp_months = calculate_experience_months(profile.work_history)
        result = score_eb2niw(profile, exp_months)
        assert result["total"] < 6
        assert result["eligible"] is False

    def test_prong_scores_in_range(self):
        profile = _make_profile()
        result = score_eb2niw(profile, exp_months=36)
        assert 0 <= result["prong1"] <= 3
        assert 0 <= result["prong2"] <= 3
        assert 0 <= result["prong3"] <= 3


# ---------------------------------------------------------------------------
# run_scoring (integration)
# ---------------------------------------------------------------------------

class TestRunScoring:
    def test_recommended_program_both(self):
        profile = _make_profile(
            awards=["IEEE Fellow", "Best Paper Award", "NSF Award"],
            publications=["Science 2022", "Nature 2021"],
            memberships=["ACM", "IEEE"],
            work_history=[
                _make_job("2015-01", "Present",
                          title="Principal AI Research Scientist",
                          responsibilities=["Led AI lab", "Peer reviewer for NeurIPS"]),
            ],
        )
        scores = run_scoring(profile)
        assert scores.recommended_program in {"EB-1A", "EB-2 NIW", "Both"}
        assert scores.experience_months > 0

    def test_score_result_fields_present(self):
        profile = _make_profile()
        scores = run_scoring(profile)
        assert isinstance(scores.eb1a_criteria_met, list)
        assert isinstance(scores.eb1a_criteria_missing, list)
        assert isinstance(scores.eb1a_total_met, int)
        assert isinstance(scores.experience_months, int)
