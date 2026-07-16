from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from backend.models import ConstraintType, FactorType, GateStatus

# ---------------------------------------------------------------------------
# Division Group
# ---------------------------------------------------------------------------
class DivisionGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=20)
    description: Optional[str] = None

class DivisionGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    is_active: Optional[bool] = None

class DivisionGroupRead(DivisionGroupCreate):
    id: int
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}

# ---------------------------------------------------------------------------
# Group Criteria (Parameter group_id dihapus dari payload penciptaan)
# ---------------------------------------------------------------------------
class GroupCriteriaCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    target_value: float = Field(..., ge=0, le=5)
    factor_type: FactorType

class GroupCriteriaRead(GroupCriteriaCreate):
    id: int
    group_id: int
    is_active: bool
    model_config = {"from_attributes": True}

# ---------------------------------------------------------------------------
# Division Criteria Weight (Parameter division_id dihapus dari payload)
# ---------------------------------------------------------------------------
class DivisionCriteriaWeightCreate(BaseModel):
    group_criteria_id: int
    weight: float = Field(..., gt=0, le=1)

class DivisionCriteriaWeightRead(DivisionCriteriaWeightCreate):
    id: int
    division_id: int
    model_config = {"from_attributes": True}

# ---------------------------------------------------------------------------
# Education Field & Constraints
# ---------------------------------------------------------------------------
class EducationFieldCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=50)
    category: Optional[str] = Field(None, max_length=100)

class EducationFieldRead(EducationFieldCreate):
    id: int
    is_active: bool
    model_config = {"from_attributes": True}

class DivisionConstraintCreate(BaseModel):
    education_field_id: int
    constraint_type: ConstraintType
    requires_interview_if_not_native: bool = False

class DivisionConstraintRead(DivisionConstraintCreate):
    id: int
    division_id: int
    model_config = {"from_attributes": True}

# ---------------------------------------------------------------------------
# Division
# ---------------------------------------------------------------------------
class DivisionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=20)
    group_id: Optional[int] = None
    monthly_budget: float = Field(0.0, ge=0.0)

class DivisionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    group_id: Optional[int] = None
    is_active: Optional[bool] = None
    monthly_budget: Optional[float] = Field(None, ge=0.0)

class DivisionRead(DivisionCreate):
    id: int
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}

# ---------------------------------------------------------------------------
# Gate & WLA Schemas (Dipertahankan di sini agar import file lain tidak rusak)
# ---------------------------------------------------------------------------
class InterviewScoreEntry(BaseModel):
    criteria_id: int  # Merujuk ke group_criteria.id
    raw_score: float = Field(..., ge=0, le=100)

class InterviewScoreSubmit(BaseModel):
    gate_id: int
    scores: list[InterviewScoreEntry] = Field(..., min_length=1)
    
class InterviewScoreRead(BaseModel):
    criteria_id: int
    raw_score: float | None = None
    score: float | None = None
    
    model_config = {"from_attributes": True, "populate_by_name": True}

class RotationGateRead(BaseModel):
    id: int
    sdm_request_id: int
    employee_id: int
    education_gate_status: str
    education_gate_notes: Optional[str]
    interview_gate_status: Optional[GateStatus]
    interview_gate_notes: Optional[str]
    is_eligible_for_matching: bool
    model_config = {"from_attributes": True}
    
    
class GateEvaluateRequest(BaseModel):
    sdm_request_id: int
    employee_id: int

class GateFailRequest(BaseModel):
    gate_id: int
    notes: str = Field(..., min_length=5)

class WLACreate(BaseModel):
    division_id: int
    period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    total_workload_hours: float = Field(..., gt=0)
    headcount: int = Field(..., gt=0)
    notes: Optional[str] = None

class WLARead(BaseModel):
    id: int
    division_id: int
    period: str
    total_workload_hours: float
    total_capacity_hours: float
    headcount: int
    wla_value: float
    is_understaffed: bool
    is_overstaffed: bool
    notes: Optional[str]
    recorded_at: datetime
    model_config = {"from_attributes": True}
    
class WLASimulationRead(BaseModel):
    division_id: int
    division_name: str
    current_wla: float
    projected_wla: float
    current_headcount: int
    projected_headcount: int
    is_safe: bool
    warning: Optional[str] = None

class RotationWLACheckRead(BaseModel):
    source: WLASimulationRead
    target: WLASimulationRead
    rotation_approved: bool