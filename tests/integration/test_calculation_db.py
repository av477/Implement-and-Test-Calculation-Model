"""Polymorphic calculation models and operations against real PostgreSQL."""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.calculations import CalculationError
from app.models import Addition, Calculation, Division, Multiplication, Subtraction, User
from app.operations import (
    UserNotFoundError,
    create_calculation,
    get_calculation,
    list_calculations,
    update_calculation,
)
from app.schemas import CalculationCreate, CalculationUpdate

pytestmark = pytest.mark.integration


@pytest.fixture
def user(db_session):
    return make_user(db_session, "calc_user")


def make_user(db, username):
    user = User(username=username, email=f"{username}@example.com", password_hash="x")
    db.add(user)
    db.commit()
    return user


def new_calc(db, user, calculation_type="Add", a=1, b=2):
    return create_calculation(
        db, CalculationCreate(a=a, b=b, type=calculation_type, user_id=user.id)
    )


def test_create_stores_computed_result(db_session, user):
    calc = new_calc(db_session, user, "Divide", 7, 2)

    assert isinstance(calc.id, uuid.UUID)
    assert calc.result == 3.5
    assert calc.created_at is not None
    assert calc.updated_at is not None
    row = db_session.execute(
        text("SELECT a, b, type, result, user_id FROM calculations WHERE id = :id"),
        {"id": calc.id},
    ).one()
    # The discriminator is stored as a readable value, and user_id as a UUID.
    assert tuple(row) == (7.0, 2.0, "Divide", 3.5, user.id)


@pytest.mark.parametrize(
    ("calculation_type", "expected_class", "expected"),
    [
        ("Add", Addition, 12),
        ("Sub", Subtraction, 8),
        ("Multiply", Multiplication, 20),
        ("Divide", Division, 5),
    ],
)
def test_database_returns_the_right_subclass(
    db_session, user, calculation_type, expected_class, expected
):
    calc_id = new_calc(db_session, user, calculation_type, 10, 2).id
    # Forget the objects in memory so the next query really reads the row.
    db_session.expunge_all()

    loaded = get_calculation(db_session, calc_id)
    assert type(loaded) is expected_class
    assert loaded.type == calculation_type
    assert loaded.result == expected


def test_query_on_base_class_returns_mixed_subclasses(db_session, user):
    for calculation_type in ["Add", "Sub", "Multiply", "Divide"]:
        new_calc(db_session, user, calculation_type, 8, 2)
    db_session.expunge_all()

    loaded = {type(c): c.result for c in list_calculations(db_session)}
    assert loaded == {Addition: 10, Subtraction: 6, Multiplication: 16, Division: 4}


def test_query_on_subclass_returns_only_that_type(db_session, user):
    new_calc(db_session, user, "Add")
    new_calc(db_session, user, "Divide", 4, 2)

    divisions = db_session.scalars(select(Division)).all()
    assert [c.type for c in divisions] == ["Divide"]


def test_calculation_belongs_to_user(db_session, user):
    calc = new_calc(db_session, user)

    assert calc.user_id == user.id
    assert calc.user.username == "calc_user"
    assert [c.id for c in user.calculations] == [calc.id]


def test_unknown_user_is_rejected(db_session):
    with pytest.raises(UserNotFoundError):
        create_calculation(
            db_session, CalculationCreate(a=1, b=2, type="Add", user_id=uuid.uuid4())
        )
    assert list_calculations(db_session) == []


def test_foreign_key_rejects_missing_user(db_session):
    """Even bypassing the app's check, PostgreSQL refuses a bad user_id."""
    db_session.add(Calculation.create("Add", 1, 2, uuid.uuid4()))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_user_id_is_required(db_session):
    db_session.add(Calculation.create("Add", 1, 2))
    with pytest.raises(IntegrityError, match="user_id"):
        db_session.commit()
    db_session.rollback()


def test_check_constraint_rejects_unknown_type(db_session, user):
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO calculations (id, user_id, type, a, b, result) "
                "VALUES (:id, :user_id, 'Power', 1, 2, 1)"
            ),
            {"id": uuid.uuid4(), "user_id": user.id},
        )
    db_session.rollback()


def test_deleting_user_deletes_their_calculations(db_session, user):
    calc_id = new_calc(db_session, user).id

    db_session.delete(user)
    db_session.commit()
    db_session.expire_all()

    assert get_calculation(db_session, calc_id) is None


def test_overflowing_result_is_not_saved(db_session, user):
    with pytest.raises(CalculationError):
        new_calc(db_session, user, "Multiply", 1e308, 10)
    assert list_calculations(db_session) == []


def test_list_calculations_filters_by_user(db_session):
    alice = make_user(db_session, "alice")
    bob = make_user(db_session, "bob")
    a1 = new_calc(db_session, alice, "Add")
    b1 = new_calc(db_session, bob, "Sub")

    assert {c.id for c in list_calculations(db_session)} == {a1.id, b1.id}
    assert [c.id for c in list_calculations(db_session, alice.id)] == [a1.id]
    assert [c.id for c in list_calculations(db_session, bob.id)] == [b1.id]


def test_update_recomputes_result_and_updated_at(db_session, user):
    calc = new_calc(db_session, user, "Multiply", 2, 3)
    created_at = calc.created_at
    # Inside one test transaction PostgreSQL's now() never changes, so set an
    # old updated_at first to see the update replace it.
    db_session.execute(
        text("UPDATE calculations SET updated_at = '2000-01-01T00:00:00Z' WHERE id = :id"),
        {"id": calc.id},
    )
    db_session.expire(calc)
    assert calc.updated_at.year == 2000

    updated = update_calculation(db_session, calc, CalculationUpdate(b=10))

    assert type(updated) is Multiplication
    assert (updated.a, updated.b, updated.result) == (2, 10, 20)
    assert updated.created_at == created_at
    assert updated.updated_at.year > 2000


def test_failed_update_leaves_calculation_unchanged(db_session, user):
    calc = new_calc(db_session, user, "Divide", 8, 2)

    with pytest.raises(CalculationError, match="divide by zero"):
        update_calculation(db_session, calc, CalculationUpdate(b=0))

    db_session.expire_all()
    loaded = get_calculation(db_session, calc.id)
    assert (loaded.a, loaded.b, loaded.result) == (8, 2, 4)
