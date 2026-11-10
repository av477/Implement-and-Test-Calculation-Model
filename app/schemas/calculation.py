"""Pydantic schemas for calculations."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, FiniteFloat, field_validator, model_validator

from app.calculations.types import CalculationType


class CalculationBase(BaseModel):
    """The numbers and the operation. Shared by the create and calculate requests."""

    # FiniteFloat rejects "inf" and "nan", which aren't real inputs.
    a: FiniteFloat
    b: FiniteFloat
    type: CalculationType

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value: Any) -> Any:
        """Accept any letter case, e.g. "add", "ADD" or " Add " all mean Add."""
        if isinstance(value, str):
            for member in CalculationType:
                if member.value.lower() == value.strip().lower():
                    return member
        return value

    @model_validator(mode="after")
    def check_divisor(self) -> "CalculationBase":
        if self.type is CalculationType.DIVIDE and self.b == 0:
            raise ValueError("b must not be zero for Divide")
        return self


class CalculationCreate(CalculationBase):
    """Data needed to save a calculation for a user."""

    user_id: UUID


class CalculationUpdate(BaseModel):
    """New numbers for an existing calculation. Its type can't change."""

    a: FiniteFloat | None = None
    b: FiniteFloat | None = None

    @model_validator(mode="after")
    def check_not_empty(self) -> "CalculationUpdate":
        if self.a is None and self.b is None:
            raise ValueError("give a new value for a, b or both")
        return self


class CalculationResult(BaseModel):
    """Answer from /calculate (nothing is saved)."""

    a: float
    b: float
    type: CalculationType
    result: float


class CalculationRead(BaseModel):
    """A stored calculation as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    type: CalculationType
    a: float
    b: float
    result: float
    created_at: datetime
    updated_at: datetime
