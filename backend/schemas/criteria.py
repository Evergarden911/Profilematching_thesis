from typing import Optional

from pydantic import BaseModel, Field, model_validator

from backend.models import FactorType


class CriteriaBase(BaseModel):
    division_id: int
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    target_value: float = Field(..., ge=0, le=5)
    weight: float = Field(..., gt=0, le=1)
    factor_type: FactorType


class CriteriaCreate(CriteriaBase):
    pass


class CriteriaUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    target_value: Optional[float] = Field(None, ge=0, le=5)
    weight: Optional[float] = Field(None, gt=0, le=1)
    factor_type: Optional[FactorType] = None
    is_active: Optional[bool] = None


class CriteriaRead(CriteriaBase):
    id: int
    is_active: bool

    model_config = {"from_attributes": True}


class CriteriaBulkCreate(BaseModel):
    """Validates that total core weights and secondary weights each sum to 1.0."""

    items: list[CriteriaCreate]

    @model_validator(mode="after")
    def validate_weight_sums(self) -> "CriteriaBulkCreate":
        core_total = sum(c.weight for c in self.items if c.factor_type == FactorType.core)
        secondary_total = sum(c.weight for c in self.items if c.factor_type == FactorType.secondary)

        tolerance = 1e-6
        if self.items:
            has_core = any(c.factor_type == FactorType.core for c in self.items)
            has_secondary = any(c.factor_type == FactorType.secondary for c in self.items)

            if has_core and abs(core_total - 1.0) > tolerance:
                raise ValueError(f"Core factor weights must sum to 1.0, got {core_total:.4f}")
            if has_secondary and abs(secondary_total - 1.0) > tolerance:
                raise ValueError(
                    f"Secondary factor weights must sum to 1.0, got {secondary_total:.4f}"
                )
        return self