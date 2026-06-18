from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


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
    start_date: Optional[str] = None   # YYYY-MM hoặc YYYY
    end_date: Optional[str] = None     # "Present" nếu đang học


class WorkExperience(BaseModel):
    job_title: str
    company: str
    country: str
    start_date: str                    # YYYY-MM
    end_date: str                      # "Present" nếu đang làm
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


class USAScoreResult(BaseModel):
    eb1a_criteria_met: List[str]
    eb1a_criteria_missing: List[str]
    eb1a_total_met: int
    eb1a_eligible: bool

    eb2niw_prong1_score: int
    eb2niw_prong2_score: int
    eb2niw_prong3_score: int
    eb2niw_total_score: int
    eb2niw_eligible: bool

    recommended_program: str           # "EB-1A", "EB-2 NIW", hoặc "Both"
    experience_months: int


class CVAnalysisResponse(BaseModel):
    profile: ImmigrationProfileSchema
    scores: USAScoreResult
    gap_report: str
    processing_time_seconds: float
