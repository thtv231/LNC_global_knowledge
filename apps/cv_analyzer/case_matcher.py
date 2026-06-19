from __future__ import annotations
import math
from dataclasses import dataclass, field as dc_field
from typing import List
from apps.cv_analyzer.schemas import ImmigrationProfileSchema, USAScoreResult, SimilarCase, DegreeLevel
from apps.cv_analyzer.case_loader import get_cases_by_program

_DEGREE_RANK_MAP = {
    DegreeLevel.PHD: 4,
    DegreeLevel.MASTERS: 3,
    DegreeLevel.POST_GRAD: 3,
    DegreeLevel.BACHELORS: 2,
    DegreeLevel.DIPLOMA: 1,
    DegreeLevel.HIGH_SCHOOL: 1,
    DegreeLevel.OTHER: 2,
}

WEIGHTS = {
    "publications": 0.35,
    "citations": 0.25,
    "degree_rank": 0.25,
    "recommendation_letters": 0.15,
}


def _profile_degree_rank(profile: ImmigrationProfileSchema) -> int:
    if not profile.education_history:
        return 2
    return max(_DEGREE_RANK_MAP.get(e.degree_level, 2) for e in profile.education_history)


def find_similar_cases(
    profile: ImmigrationProfileSchema,
    scores: USAScoreResult,
    program: str,
    top_k: int = 5,
) -> List[SimilarCase]:
    cases = get_cases_by_program(program)
    if not cases:
        return []

    pub_count = len(profile.publications)
    citation_count = 0
    letter_count = len(profile.certifications)
    degree_rank = _profile_degree_rank(profile)

    max_pub = max((c["publications"] for c in cases), default=1) or 1
    max_cit = max((c["citations"] for c in cases), default=1) or 1
    max_let = max((c["recommendation_letters"] for c in cases), default=1) or 1

    profile_vec = [
        pub_count / max_pub,
        citation_count / max_cit,
        degree_rank / 4,
        letter_count / max_let,
    ]
    weights = list(WEIGHTS.values())

    scored = []
    for case in cases:
        case_vec = [
            case["publications"] / max_pub,
            case["citations"] / max_cit,
            case["degree_rank"] / 4,
            case["recommendation_letters"] / max_let,
        ]
        dist = math.sqrt(sum(w * (p - c) ** 2 for w, p, c in zip(weights, profile_vec, case_vec)))
        similarity = 1.0 / (1.0 + dist)
        scored.append((similarity, case))

    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for sim_score, c in scored[:top_k]:
        breakdown = {
            "publications_profile": pub_count,
            "publications_case": int(c["publications"]),
            "citations_profile": citation_count,
            "citations_case": int(c["citations"]),
            "degree_rank_profile": degree_rank,
            "degree_rank_case": int(c["degree_rank"]),
        }
        results.append(SimilarCase(
            program=c["program"],
            field=c["field"],
            degree=c["degree"],
            current_role=c["current_role"],
            publications=int(c["publications"]),
            citations=int(c["citations"]),
            recommendation_letters=int(c["recommendation_letters"]),
            post_rfe=c["post_rfe"],
            approval_date=c["approval_date"],
            processing_days=c["processing_days"],
            premium_processing=c["premium_processing"],
            notable=c["notable"],
            source_url=c["source_url"],
            similarity_score=round(sim_score, 4),
            similarity_breakdown=breakdown,
        ))

    return results
