from pydantic import BaseModel
from typing import Optional

class ConstraintBase(BaseModel):
    division_id: int
    education_field_id: int
    constraint_type: str  # Berisi nilai 'allowed' atau 'blocked'
    requires_interview_if_not_native: bool = False

class ConstraintCreate(ConstraintBase):
    pass

class ConstraintRead(ConstraintBase):
    id: int
    division_name: Optional[str] = None
    education_field_name: Optional[str] = None

    class Config:
        from_attributes = True
        
class EducationFieldCreate(BaseModel):
    name: str
    code: str
    category: str