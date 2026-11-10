"""Pydantic schemas for calculations."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.calculations.factory import CalculationType


class CalculationCreate(BaseModel):
    """Data needed to create a calculation."""

    # allow_inf_nan=False rejects "inf" and "nan", which aren't real inputs.
    a: float = Field(allow_inf_nan=False)
    b: float = Field(allow_inf_nan=False)
    type: CalculationType
    user_id: int | None = Field(default=None, gt=0)

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
    def check_divisor(self) -> "CalculationCreate":
        if self.type is CalculationType.DIVIDE and self.b == 0:
            raise ValueError("b must not be zero for Divide")
        return self


class CalculationRead(BaseModel):
    """A stored calculation as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    a: float
    b: float
    type: CalculationType
    result: float
    user_id: int | None
    created_at: datetime
