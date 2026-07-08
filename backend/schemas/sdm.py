from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from backend.models import RequestStatus, GateStatus
from backend.schemas.employee import EmployeeRead


# ---------------------------------------------------------------------------
# SDM Request
# ---------------------------------------------------------------------------


class SDMRequestCreate(BaseModel):
    target_division_id: int
    quantity: int = Field(..., ge=1)
    reason: str = Field(..., min_length=10)
    is_auto_generated: bool = Field(False, description="True jika dibuat otomatis oleh sistem WLA")


class SDMRequestUpdate(BaseModel):
    status: Optional[RequestStatus] = None
    hrd_notes: Optional[str] = None
    budget_gate_status: Optional[GateStatus] = None # PARAMETER BARU
    budget_notes: Optional[str] = None # PARAMETER BARU


class SDMRequestRead(BaseModel):
    id: int
    requester_id: int
    target_division_id: int
    quantity: int
    reason: str
    status: RequestStatus
    
    # PARAMETER BARU
    budget_gate_status: GateStatus 
    budget_notes: Optional[str]
    is_auto_generated: bool
    
    hrd_notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Matching Result
# ---------------------------------------------------------------------------


class MatchingResultRead(BaseModel):
    id: int
    sdm_request_id: int
    employee_id: int
    ncf_score: float
    nsf_score: float
    final_score: float
    rank: int
    computed_at: datetime
    employee: EmployeeRead

    model_config = {"from_attributes": True}


class MatchingResultSummary(BaseModel):
    """Lightweight version for list views."""

    rank: int
    employee_id: int
    employee_name: str
    final_score: float
    ncf_score: float
    nsf_score: float


# ---------------------------------------------------------------------------
# Transfer Letter
# ---------------------------------------------------------------------------


class TransferLetterCreate(BaseModel):
    sdm_request_id: int
    letter_number: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=10)


class TransferLetterRead(BaseModel):
    id: int
    sdm_request_id: int
    issued_by_id: int
    letter_number: str
    content: str
    created_at: datetime  # Diperbaiki dari issued_at agar sesuai dengan model ORM

    model_config = {"from_attributes": True}