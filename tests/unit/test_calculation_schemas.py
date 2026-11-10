"""Pydantic validation for the calculation schemas."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.calculations import CalculationType
from app.schemas import (
    CalculationBase,
    CalculationCreate,
    CalculationRead,
    CalculationResult,
    CalculationUpdate,
)

pytestmark = pytest.mark.unit

USER_ID = uuid.uuid4()
VALID = {"a": 6, "b": 3, "type": "Divide", "user_id": str(USER_ID)}


def make(**overrides):
    return CalculationCreate(**{**VALID, **overrides})


def test_valid_calculation_create():
    calc = make()
    assert calc.a == 6.0
    assert calc.b == 3.0
    assert calc.type is CalculationType.DIVIDE
    assert calc.user_id == USER_ID


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


@pytest.mark.parametrize("field", ["a", "b", "type", "user_id"])
def test_missing_field_is_rejected(field):
    data = dict(VALID)
    del data[field]
    with pytest.raises(ValidationError):
        CalculationCreate(**data)


@pytest.mark.parametrize("value", ["abc", float("inf"), float("nan"), [1], None])
def test_non_numeric_operand_is_rejected(value):
    with pytest.raises(ValidationError):
        make(a=value)


@pytest.mark.parametrize("user_id", [0, 1, "x", "not-a-uuid", None])
def test_invalid_user_id_is_rejected(user_id):
    with pytest.raises(ValidationError):
        make(user_id=user_id)


def test_base_schema_needs_no_user():
    calc = CalculationBase(a=1, b=2, type="add")
    assert calc.type is CalculationType.ADD
    assert not hasattr(calc, "user_id")


def test_update_accepts_one_or_both_numbers():
    assert CalculationUpdate(a=5).model_dump() == {"a": 5, "b": None}
    assert CalculationUpdate(a=5, b=0).model_dump() == {"a": 5, "b": 0}


@pytest.mark.parametrize("payload", [{}, {"a": None, "b": None}, {"a": "x"}, {"b": float("inf")}])
def test_update_rejects_empty_or_bad_values(payload):
    with pytest.raises(ValidationError):
        CalculationUpdate(**payload)


def test_calculation_result():
    body = CalculationResult(a=1, b=2, type="Add", result=3).model_dump(mode="json")
    assert body == {"a": 1.0, "b": 2.0, "type": "Add", "result": 3.0}


def test_calculation_read_from_orm_object():
    now = datetime.now(timezone.utc)
    stored = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=USER_ID,
        type="Divide",
        a=6.0,
        b=3.0,
        result=2.0,
        created_at=now,
        updated_at=now,
    )
    data = CalculationRead.model_validate(stored).model_dump(mode="json")
    assert data["type"] == "Divide"
    assert data["user_id"] == str(USER_ID)
    assert set(data) == {"id", "user_id", "type", "a", "b", "result", "created_at", "updated_at"}
