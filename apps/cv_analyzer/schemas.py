from __future__ import annotations
from dataclasses import dataclass, field as dc_field
from typing import List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class DegreeLevel(str, Enum):
    PHD = "Doctorate (PhD)"
    MASTERS = "Master's Degree"
    POST_GRAD = "Post-Graduate Diploma/Certificate"
    BACHELORS = "Bachelor's Degree"
    DIPLOMA = "Two-Year College/Technical Diploma"
    HIGH_SCHOOL = "High School Graduation"
    OTHER = "Other/Unspecified"


class LanguageTestType(str, Enum):
    IELTS = "IELTS"
    PTE = "PTE Academic"
    CELPIP = "CELPIP"
    TEF = "TEF (French)"
    TCF = "TCF (French)"
    NONE = "Not Mentioned"


class LanguageProficiency(BaseModel):
    test_type: LanguageTestType = Field(default=LanguageTestType.NONE)
    overall: Optional[float] = None
    listening: Optional[float] = None
    reading: Optional[float] = None
    writing: Optional[float] = None
    speaking: Optional[float] = None


class EducationInfo(BaseModel):
    degree_level: DegreeLevel
    field_of_study: str
    institution: str
    country: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class WorkExperience(BaseModel):
    job_title: str
    company: str
    country: str
    start_date: str
    end_date: str
    is_full_time: bool = True
    main_responsibilities: List[str]


class ImmigrationProfileSchema(BaseModel):
    full_name: str
    age: Optional[int] = None
    current_country: Optional[str] = None
    language_skills: List[LanguageProficiency] = []
    education_history: List[EducationInfo]
    work_history: List[WorkExperience]
    certifications: List[str] = []
    publications: List[str] = []
    awards: List[str] = []
    patents: List[str] = []
    media_coverage: List[str] = []
    speaking_engagements: List[str] = []
    memberships: List[str] = []

    @field_validator("language_skills", mode="before")
    @classmethod
    def coerce_language_skills(cls, v: Any) -> Any:
        if not isinstance(v, list):
            return []
        result = []
        for item in v:
            if isinstance(item, str):
                result.append({"test_type": "Not Mentioned"})
            elif isinstance(item, dict):
                result.append(item)
            else:
                result.append(item)
        return result

    @field_validator("education_history", "work_history", mode="before")
    @classmethod
    def ensure_list(cls, v: Any) -> Any:
        if v is None:
            return []
        return v

    @field_validator(
        "certifications", "publications", "awards", "patents",
        "media_coverage", "speaking_engagements", "memberships",
        mode="before",
    )
    @classmethod
    def coerce_str_list(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(i) for i in v if i is not None]
        return []


class USAScoreResult(BaseModel):
    eb1a_criteria_met: List[str]
    eb1a_criteria_missing: List[str]
    eb1a_total_met: int
    eb1a_eligible: bool
    eb1a_risk_label: str = ""       # e.g. "Rủi ro rất cao (RFE ~90%)"
    eb1a_risk_level: str = ""       # "danger" | "warning" | "ok" | "strong"

    eb2niw_prong1_score: int
    eb2niw_prong2_score: int
    eb2niw_prong3_score: int
    eb2niw_total_score: int
    eb2niw_eligible: bool
    eb2niw_strength_label: str = "" # e.g. "Khả thi — cần bổ sung gap"
    eb2niw_strength_level: str = "" # "weak" | "fair" | "good" | "strong"

    recommended_program: str
    experience_months: int


@dataclass
class SimilarCase:
    program: str
    field: str
    degree: str
    current_role: str
    publications: int
    citations: int
    recommendation_letters: int
    post_rfe: bool
    approval_date: str
    processing_days: float
    premium_processing: str
    notable: str
    source_url: str
    similarity_score: float
    similarity_breakdown: dict = dc_field(default_factory=dict)


class CVAnalysisResponse(BaseModel):
    profile: ImmigrationProfileSchema
    scores: USAScoreResult
    similar_cases_eb1a: List[dict] = []
    similar_cases_niw: List[dict] = []
    gap_report: str
    drive_folder_url: str = ""
    processing_time_seconds: float
