"""Polymorphic models and the factory, tested without a database."""

import uuid

import pytest

from app.calculations import CalculationError, CalculationType
from app.models import Addition, Calculation, Division, Multiplication, Subtraction

pytestmark = pytest.mark.unit

SUBCLASSES = [
    (CalculationType.ADD, Addition),
    (CalculationType.SUB, Subtraction),
    (CalculationType.MULTIPLY, Multiplication),
    (CalculationType.DIVIDE, Division),
]


@pytest.mark.parametrize(("calculation_type", "expected_class"), SUBCLASSES)
def test_factory_returns_matching_subclass(calculation_type, expected_class):
    calc = Calculation.create(calculation_type, 6, 3)

    assert type(calc) is expected_class
    assert isinstance(calc, Calculation)
    # The discriminator column is filled in from the subclass.
    assert calc.type == calculation_type.value


@pytest.mark.parametrize(("calculation_type", "expected_class"), SUBCLASSES)
def test_factory_accepts_string_value(calculation_type, expected_class):
    assert Calculation.subclass_for(calculation_type.value) is expected_class


@pytest.mark.parametrize("bad_type", ["Power", "add", "", None, 42])
def test_factory_rejects_unknown_type(bad_type):
    with pytest.raises(CalculationError, match="Unsupported calculation type"):
        Calculation.create(bad_type, 1, 2)


def test_factory_sets_fields():
    user_id = uuid.uuid4()
    calc = Calculation.create("Add", 1.5, 2, user_id)
    assert (calc.a, calc.b, calc.result, calc.user_id) == (1.5, 2, 3.5, user_id)


@pytest.mark.parametrize(
    ("calculation_type", "a", "b", "expected"),
    [
        ("Add", 2, 3, 5),
        ("Add", -1.5, 0.5, -1.0),
        ("Sub", 10, 4, 6),
        ("Sub", 4, 10, -6),
        ("Multiply", 3, -4, -12),
        ("Multiply", 2.5, 0, 0),
        ("Divide", 10, 4, 2.5),
        ("Divide", -9, 3, -3),
    ],
)
def test_results(calculation_type, a, b, expected):
    assert Calculation.create(calculation_type, a, b).result == pytest.approx(expected)


@pytest.mark.parametrize("zero", [0, 0.0, -0.0])
def test_divide_by_zero_is_rejected(zero):
    with pytest.raises(CalculationError, match="divide by zero"):
        Calculation.create("Divide", 1, zero)


@pytest.mark.parametrize(
    ("calculation_type", "a", "b"),
    [
        ("Add", 1e308, 1e308),
        ("Sub", -1e308, 1e308),
        ("Multiply", 1e308, 10),
        ("Divide", 1e308, 1e-10),
    ],
)
def test_result_too_large_is_rejected(calculation_type, a, b):
    with pytest.raises(CalculationError, match="too large"):
        Calculation.create(calculation_type, a, b)


def test_overflow_error_becomes_calculation_error(monkeypatch):
    def explode(self, a, b):
        raise OverflowError

    monkeypatch.setattr(Addition, "_apply", explode)
    with pytest.raises(CalculationError, match="too large"):
        Calculation.create("Add", 1, 2)


def test_compute_reuses_the_subclass_logic():
    calc = Calculation.create("Sub", 10, 1)
    assert calc.compute(5, 2) == 3


def test_base_class_has_no_math():
    with pytest.raises(NotImplementedError):
        Calculation(a=1, b=2).compute(1, 2)


def test_repr_names_the_subclass():
    calc = Calculation.create("Multiply", 2, 3)
    assert repr(calc) == "<Multiplication id=None 2 * 3 = 6>"


# ----- @validates: the ORM-level check on a and b -------------------------


@pytest.mark.parametrize("field", ["a", "b"])
@pytest.mark.parametrize(
    ("value", "message"),
    [
        (float("inf"), "must be a finite number"),
        (float("-inf"), "must be a finite number"),
        (float("nan"), "must be a finite number"),
        ("5", "must be a number"),
        (None, "must be a number"),
        (True, "must be a number"),
    ],
)
def test_validates_rejects_bad_numbers(field, value, message):
    numbers = {"a": 1, "b": 2, field: value}
    with pytest.raises(CalculationError, match=f"{field} {message}"):
        Calculation.create("Add", numbers["a"], numbers["b"])


def test_validates_runs_when_attribute_changes():
    calc = Calculation.create("Add", 1, 2)
    with pytest.raises(CalculationError, match="b must be a finite number"):
        calc.b = float("nan")
    assert calc.b == 2


def test_validates_stores_floats():
    calc = Calculation.create("Add", 1, 2)
    assert isinstance(calc.a, float) and isinstance(calc.b, float)


# ----- hybrid_property, Python side ----------------------------------------


@pytest.mark.parametrize(
    ("calculation_type", "a", "b", "expected"),
    [
        ("Add", 6, 3, "6 + 3"),
        ("Sub", 6, -3, "6 - -3"),
        ("Multiply", 2.5, 4, "2.5 * 4"),
        ("Divide", 1, 3, "1 / 3"),
        ("Add", 0.1, 1e-05, "0.1 + 1e-05"),
        ("Add", -0.0, 1e20, "-0 + 1e+20"),
    ],
)
def test_expression_in_python(calculation_type, a, b, expected):
    assert Calculation.create(calculation_type, a, b).expression == expected
