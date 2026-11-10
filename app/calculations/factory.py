"""Calculation logic built with the Factory pattern.

Each kind of calculation (Add, Sub, Multiply, Divide) is its own small class
with a ``compute(a, b)`` method. ``CalculationFactory.create(type)`` picks the
right class for a ``CalculationType``, so the rest of the app never needs an
``if type == ...`` chain. Adding a new operation means writing one class and
registering it in the factory.
"""

import math
from abc import ABC, abstractmethod
from enum import Enum


class CalculationType(str, Enum):
    """The calculation types the API accepts."""

    ADD = "Add"
    SUB = "Sub"
    MULTIPLY = "Multiply"
    DIVIDE = "Divide"


class CalculationError(ValueError):
    """Raised when a calculation can't produce a valid number."""


class Operation(ABC):
    """Base class for one kind of calculation."""

    @abstractmethod
    def _apply(self, a: float, b: float) -> float:
        """Return the raw result of the operation."""

    def compute(self, a: float, b: float) -> float:
        """Return the result, rejecting answers that are not finite numbers."""
        try:
            result = self._apply(a, b)
        except OverflowError as exc:
            raise CalculationError("Result is too large to store") from exc
        if not math.isfinite(result):
            raise CalculationError("Result is too large to store")
        return result


class AddOperation(Operation):
    def _apply(self, a: float, b: float) -> float:
        return a + b


class SubOperation(Operation):
    def _apply(self, a: float, b: float) -> float:
        return a - b


class MultiplyOperation(Operation):
    def _apply(self, a: float, b: float) -> float:
        return a * b


class DivideOperation(Operation):
    def _apply(self, a: float, b: float) -> float:
        if b == 0:
            raise CalculationError("Cannot divide by zero")
        return a / b


class CalculationFactory:
    """Creates the right ``Operation`` object for a ``CalculationType``."""

    _operations: dict[CalculationType, type[Operation]] = {
        CalculationType.ADD: AddOperation,
        CalculationType.SUB: SubOperation,
        CalculationType.MULTIPLY: MultiplyOperation,
        CalculationType.DIVIDE: DivideOperation,
    }

    @classmethod
    def create(cls, calculation_type: CalculationType | str) -> Operation:
        """Return an operation object for ``calculation_type`` (enum or its string value)."""
        try:
            return cls._operations[CalculationType(calculation_type)]()
        except (KeyError, ValueError) as exc:
            raise CalculationError(f"Unsupported calculation type: {calculation_type!r}") from exc


def compute_result(calculation_type: CalculationType | str, a: float, b: float) -> float:
    """Shortcut: build the operation with the factory and run it."""
    return CalculationFactory.create(calculation_type).compute(a, b)
