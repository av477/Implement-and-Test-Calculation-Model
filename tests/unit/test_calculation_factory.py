"""Factory and operation classes: pure Python, no database."""

import pytest

from app.calculations import (
    AddOperation,
    CalculationError,
    CalculationFactory,
    CalculationType,
    DivideOperation,
    MultiplyOperation,
    Operation,
    SubOperation,
    compute_result,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("calculation_type", "expected_class"),
    [
        (CalculationType.ADD, AddOperation),
        (CalculationType.SUB, SubOperation),
        (CalculationType.MULTIPLY, MultiplyOperation),
        (CalculationType.DIVIDE, DivideOperation),
    ],
)
def test_factory_returns_matching_operation(calculation_type, expected_class):
    operation = CalculationFactory.create(calculation_type)
    assert isinstance(operation, expected_class)
    assert isinstance(operation, Operation)


def test_factory_accepts_string_value():
    assert isinstance(CalculationFactory.create("Multiply"), MultiplyOperation)


@pytest.mark.parametrize("bad_type", ["Power", "add", "", None, 42])
def test_factory_rejects_unknown_type(bad_type):
    with pytest.raises(CalculationError, match="Unsupported calculation type"):
        CalculationFactory.create(bad_type)


@pytest.mark.parametrize(
    ("calculation_type", "a", "b", "expected"),
    [
        (CalculationType.ADD, 2, 3, 5),
        (CalculationType.ADD, -1.5, 0.5, -1.0),
        (CalculationType.SUB, 10, 4, 6),
        (CalculationType.SUB, 4, 10, -6),
        (CalculationType.MULTIPLY, 3, -4, -12),
        (CalculationType.MULTIPLY, 2.5, 0, 0),
        (CalculationType.DIVIDE, 10, 4, 2.5),
        (CalculationType.DIVIDE, -9, 3, -3),
    ],
)
def test_compute_result(calculation_type, a, b, expected):
    assert compute_result(calculation_type, a, b) == pytest.approx(expected)


@pytest.mark.parametrize("zero", [0, 0.0, -0.0])
def test_divide_by_zero_is_rejected(zero):
    with pytest.raises(CalculationError, match="divide by zero"):
        DivideOperation().compute(1, zero)


@pytest.mark.parametrize(
    ("calculation_type", "a", "b"),
    [
        (CalculationType.ADD, 1e308, 1e308),
        (CalculationType.SUB, -1e308, 1e308),
        (CalculationType.MULTIPLY, 1e308, 10),
        (CalculationType.DIVIDE, 1e308, 1e-10),
    ],
)
def test_result_too_large_is_rejected(calculation_type, a, b):
    with pytest.raises(CalculationError, match="too large"):
        compute_result(calculation_type, a, b)


def test_overflow_error_becomes_calculation_error():
    class Exploding(Operation):
        def _apply(self, a, b):
            raise OverflowError

    with pytest.raises(CalculationError, match="too large"):
        Exploding().compute(1, 2)
