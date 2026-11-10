"""Calculation model and operations against a real PostgreSQL database."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.calculations import CalculationError, CalculationType
from app.models import Calculation, User
from app.operations import (
    UserNotFoundError,
    create_calculation,
    get_calculation,
    list_calculations,
)
from app.schemas import CalculationCreate

pytestmark = pytest.mark.integration


def make_user(db, username="calc_user"):
    user = User(username=username, email=f"{username}@example.com", password_hash="x")
    db.add(user)
    db.commit()
    return user


def test_create_calculation_stores_computed_result(db_session):
    calc = create_calculation(db_session, CalculationCreate(a=7, b=2, type="Divide"))

    assert calc.id is not None
    assert calc.result == 3.5
    assert calc.created_at is not None
    row = db_session.execute(
        text("SELECT a, b, type, result FROM calculations WHERE id = :id"), {"id": calc.id}
    ).one()
    # The enum is stored as its readable value.
    assert tuple(row) == (7.0, 2.0, "Divide", 3.5)


@pytest.mark.parametrize(
    ("calculation_type", "expected"),
    [("Add", 12), ("Sub", 8), ("Multiply", 20), ("Divide", 5)],
)
def test_each_type_round_trips(db_session, calculation_type, expected):
    calc = create_calculation(
        db_session, CalculationCreate(a=10, b=2, type=calculation_type)
    )
    db_session.expire_all()

    loaded = get_calculation(db_session, calc.id)
    assert loaded.type is CalculationType(calculation_type)
    assert loaded.result == expected


def test_calculation_linked_to_user(db_session):
    user = make_user(db_session)
    calc = create_calculation(
        db_session, CalculationCreate(a=1, b=2, type="Add", user_id=user.id)
    )

    assert calc.user_id == user.id
    assert calc.user.username == "calc_user"
    assert [c.id for c in user.calculations] == [calc.id]


def test_unknown_user_is_rejected(db_session):
    with pytest.raises(UserNotFoundError):
        create_calculation(db_session, CalculationCreate(a=1, b=2, type="Add", user_id=999999))
    assert list_calculations(db_session) == []


def test_foreign_key_rejects_missing_user(db_session):
    """Even bypassing the app's check, PostgreSQL refuses a bad user_id."""
    db_session.add(Calculation(a=1, b=2, type=CalculationType.ADD, result=3, user_id=999999))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_check_constraint_rejects_unknown_type(db_session):
    with pytest.raises(IntegrityError):
        db_session.execute(
            text("INSERT INTO calculations (a, b, type, result) VALUES (1, 2, 'Power', 1)")
        )
    db_session.rollback()


def test_deleting_user_deletes_their_calculations(db_session):
    user = make_user(db_session)
    calc_id = create_calculation(
        db_session, CalculationCreate(a=1, b=2, type="Add", user_id=user.id)
    ).id

    db_session.delete(user)
    db_session.commit()
    db_session.expire_all()

    assert get_calculation(db_session, calc_id) is None


def test_overflowing_result_is_not_saved(db_session):
    with pytest.raises(CalculationError):
        create_calculation(db_session, CalculationCreate(a=1e308, b=10, type="Multiply"))
    assert list_calculations(db_session) == []


def test_list_calculations_filters_by_user(db_session):
    alice = make_user(db_session, "alice")
    bob = make_user(db_session, "bob")
    a1 = create_calculation(db_session, CalculationCreate(a=1, b=1, type="Add", user_id=alice.id))
    b1 = create_calculation(db_session, CalculationCreate(a=2, b=2, type="Sub", user_id=bob.id))
    none = create_calculation(db_session, CalculationCreate(a=3, b=3, type="Multiply"))

    assert [c.id for c in list_calculations(db_session)] == [a1.id, b1.id, none.id]
    assert [c.id for c in list_calculations(db_session, alice.id)] == [a1.id]
    assert [c.id for c in list_calculations(db_session, bob.id)] == [b1.id]


def test_repr(db_session):
    calc = create_calculation(db_session, CalculationCreate(a=1, b=2, type="Add"))
    assert repr(calc) == f"<Calculation id={calc.id} 1.0 Add 2.0 = 3.0>"
