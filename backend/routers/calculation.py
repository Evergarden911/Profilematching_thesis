"""
Calculation Router
==================
Exposes the profile-matching algorithm for ad-hoc computation without
persisting results to the database. Useful for previewing or testing
criteria configurations.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.core.security import get_current_user
from backend.services.profile_matching import CriteriaInput, EmployeeMatchResult, compute_match, rank_employees

router = APIRouter(prefix="/api/calculation", tags=["calculation"])


class CriteriaInputPayload(BaseModel):
    criteria_id: int
    employee_score: float = Field(..., ge=0, le=5)
    target_value: float = Field(..., ge=0, le=5)
    weight: float = Field(..., gt=0, le=1)
    factor_type: str = Field(..., pattern="^(core|secondary)$")


class SingleMatchRequest(BaseModel):
    employee_id: int
    criteria: list[CriteriaInputPayload]


class SingleMatchResponse(BaseModel):
    employee_id: int
    ncf_score: float
    nsf_score: float
    final_score: float
    gap_detail: dict[int, float]


class BulkMatchRequest(BaseModel):
    employees: list[SingleMatchRequest]


class RankedMatchResponse(SingleMatchResponse):
    rank: int


@router.post("/single", response_model=SingleMatchResponse)
def calculate_single(
    payload: SingleMatchRequest,
    _=Depends(get_current_user),
):
    """Compute profile match score for a single employee."""
    inputs = [CriteriaInput(**c.model_dump()) for c in payload.criteria]
    result = compute_match(payload.employee_id, inputs)
    return SingleMatchResponse(
        employee_id=result.employee_id,
        ncf_score=result.ncf_score,
        nsf_score=result.nsf_score,
        final_score=result.final_score,
        gap_detail=result.gap_detail,
    )


@router.post("/rank", response_model=list[RankedMatchResponse])
def calculate_and_rank(
    payload: BulkMatchRequest,
    _=Depends(get_current_user),
):
    """Compute and rank profile match scores for multiple employees."""
    raw_results = []
    for emp in payload.employees:
        inputs = [CriteriaInput(**c.model_dump()) for c in emp.criteria]
        raw_results.append(compute_match(emp.employee_id, inputs))

    ranked = rank_employees(raw_results)
    return [
        RankedMatchResponse(
            rank=rank,
            employee_id=r.employee_id,
            ncf_score=r.ncf_score,
            nsf_score=r.nsf_score,
            final_score=r.final_score,
            gap_detail=r.gap_detail,
        )
        for rank, r in ranked
    ]