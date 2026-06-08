from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from backend.models import UserRole


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=200)
    role: UserRole
    division_id: Optional[int] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=200)
    is_active: Optional[bool] = None
    division_id: Optional[int] = None


class UserRead(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}