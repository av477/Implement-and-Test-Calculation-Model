"""Pydantic validation for CalculationCreate and CalculationRead."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.calculations import CalculationType
from app.schemas import CalculationCreate, CalculationRead

pytestmark = pytest.mark.unit

VALID = {"a": 6, "b": 3, "type": "Divide"}


def make(**overrides):
    return CalculationCreate(**{**VALID, **overrides})


def test_valid_calculation_create():
    calc = make()
    assert calc.a == 6.0
    assert calc.b == 3.0
    assert calc.type is CalculationType.DIVIDE
    assert calc.user_id is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Add", CalculationType.ADD),
        ("add", CalculationType.ADD),
        (" SUB ", CalculationType.SUB),
        ("multiply", CalculationType.MULTIPLY),
        ("DIVIDE", CalculationType.DIVIDE),
        (CalculationType.MULTIPLY, CalculationType.MULTIPLY),
    ],
)
def test_type_is_case_insensitive(raw, expected):
    assert make(type=raw).type is expected


@pytest.mark.parametrize("bad_type", ["Power", "plus", "", "Subtract", 1, None])
def test_invalid_type_is_rejected(bad_type):
    with pytest.raises(ValidationError):
        make(type=bad_type)


@pytest.mark.parametrize("zero", [0, 0.0, "0", -0.0])
def test_divide_by_zero_is_rejected(zero):
    with pytest.raises(ValidationError, match="b must not be zero"):
        make(b=zero)


@pytest.mark.parametrize("calculation_type", ["Add", "Sub", "Multiply"])
def test_zero_b_is_fine_for_other_types(calculation_type):
    assert make(type=calculation_type, b=0).b == 0


@pytest.mark.parametrize("field", ["a", "b", "type"])
def test_missing_field_is_rejected(field):
    data = dict(VALID)
    del data[field]
    with pytest.raises(ValidationError):
        CalculationCreate(**data)


@pytest.mark.parametrize("value", ["abc", float("inf"), float("nan"), [1], None])
def test_non_numeric_operand_is_rejected(value):
    with pytest.raises(ValidationError):
        make(a=value)


@pytest.mark.parametrize("user_id", [0, -1, "x"])
def test_invalid_user_id_is_rejected(user_id):
    with pytest.raises(ValidationError):
        make(user_id=user_id)


def test_calculation_read_from_orm_object():
    stored = SimpleNamespace(
        id=1,
        a=6.0,
        b=3.0,
        type=CalculationType.DIVIDE,
        result=2.0,
        user_id=None,
        created_at=datetime.now(timezone.utc),
    )
    calc = CalculationRead.model_validate(stored)
    assert calc.model_dump(mode="json")["type"] == "Divide"
    assert calc.result == 2.0
