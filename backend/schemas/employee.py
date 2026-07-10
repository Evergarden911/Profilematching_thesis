from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

# --- Skema Score (Tidak berubah) ---
class EmployeeScoreBase(BaseModel):
    criteria_id: int
    score: float = Field(..., ge=0, le=5)

class EmployeeScoreCreate(EmployeeScoreBase):
    pass

class EmployeeScoreRead(EmployeeScoreBase):
    id: int
    employee_id: int
    model_config = {"from_attributes": True}


# --- TAMBAHAN BARU: Skema Minimal untuk Relasi ---
# Skema ini berfungsi agar Pydantic bisa otomatis membaca relasi
# emp.division dan emp.division.group dari ORM SQLAlchemy.
class GroupMinimal(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}

class DivisionMinimal(BaseModel):
    id: int
    name: str
    group_id: int
    group: Optional[GroupMinimal] = None
    model_config = {"from_attributes": True}


# --- Skema Utama ---
class EmployeeBase(BaseModel):
    employee_code: str = Field(..., min_length=1, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=200)
    division_id: int
    education_field_id: int
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
    
    # TAMBAHAN: Kita butuh ini agar endpoint PATCH bisa menerima skor
    scores: Optional[list[EmployeeScoreCreate]] = None

class EmployeeRead(EmployeeBase):
    id: int
    is_active: bool
    
    # TAMBAHAN: Ekspos skor dan relasi divisi/grup ke Frontend
    scores: list[EmployeeScoreRead] = []
    division: Optional[DivisionMinimal] = None
    
    model_config = {"from_attributes": True}