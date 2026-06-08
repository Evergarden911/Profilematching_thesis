from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EmployeeScoreBase(BaseModel):
    criteria_id: int
    score: float = Field(..., ge=0, le=5)


class EmployeeScoreCreate(EmployeeScoreBase):
    pass


class EmployeeScoreRead(EmployeeScoreBase):
    id: int
    employee_id: int

    model_config = {"from_attributes": True}


class EmployeeBase(BaseModel):
    employee_code: str = Field(..., min_length=1, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=200)
    division_id: int
    education_field_id: int  # nullable=False on Employee model — required on create
    position: str = Field(..., min_length=1, max_length=150)
    has_sanction: bool = False
    base_salary: float = Field(0.0, ge=0.0, description="Beban biaya gaji per bulan")


class EmployeeCreate(EmployeeBase):
    scores: list[EmployeeScoreCreate] = []


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=200)
    division_id: Optional[int] = None
    education_field_id: Optional[int] = None
    position: Optional[str] = Field(None, min_length=1, max_length=150)
    is_active: Optional[bool] = None
    has_sanction: Optional[bool] = None
    base_salary: Optional[float] = Field(None, ge=0.0)


class EmployeeRead(EmployeeBase):
    id: int
    is_active: bool
    created_at: datetime
    # updated_at omitted — column does not exist on Employee model
    scores: list[EmployeeScoreRead] = []

    model_config = {"from_attributes": True}