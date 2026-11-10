"""Calculation types and errors, shared by the models and the schemas."""

from enum import Enum


class CalculationType(str, Enum):
    """The calculation types the API accepts. Each value is also the
    ``polymorphic_identity`` of one SQLAlchemy subclass."""

    ADD = "Add"
    SUB = "Sub"
    MULTIPLY = "Multiply"
    DIVIDE = "Divide"


class CalculationError(ValueError):
    """Raised when a calculation can't produce a valid number."""
