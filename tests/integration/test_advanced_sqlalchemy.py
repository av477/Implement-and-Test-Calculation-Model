"""Advanced SQLAlchemy features against real PostgreSQL: CHECK constraint,
@validates, hybrid_property, composite index, selectinload, column_property."""

import uuid
from contextlib import contextmanager

import pytest
from sqlalchemy import event, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.calculations import CalculationError
from app.database import engine
from app.models import Calculation, User
from app.operations import create_calculation, get_user, get_user_with_calculations
from app.schemas import CalculationCreate

pytestmark = pytest.mark.integration


def make_user(db, username="adv_user"):
    user = User(username=username, email=f"{username}@example.com", password_hash="x")
    db.add(user)
    db.commit()
    return user


def add(db, user, calculation_type, a, b):
    return create_calculation(
        db, CalculationCreate(a=a, b=b, type=calculation_type, user_id=user.id)
    )


@contextmanager
def count_queries():
    """Count the SQL statements sent to the database inside the block."""
    statements = []

    def record(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)


# ----- Table-level CHECK constraint ---------------------------------------


def insert_raw(db, user, calculation_type, b):
    """Insert straight into the table, skipping Pydantic and the ORM."""
    db.execute(
        text(
            "INSERT INTO calculations (id, user_id, type, a, b, result) "
            "VALUES (:id, :user_id, :type, 1, :b, 0)"
        ),
        {"id": uuid.uuid4(), "user_id": user.id, "type": calculation_type, "b": b},
    )


@pytest.mark.parametrize("zero", [0, 0.0, -0.0])
def test_database_rejects_divide_by_zero(db_session, zero):
    user = make_user(db_session)
    with pytest.raises(IntegrityError, match="ck_calculations_no_zero_divisor"):
        insert_raw(db_session, user, "Divide", zero)
    db_session.rollback()


@pytest.mark.parametrize("calculation_type", ["Add", "Sub", "Multiply"])
def test_database_allows_zero_b_for_other_types(db_session, calculation_type):
    user = make_user(db_session)
    insert_raw(db_session, user, calculation_type, 0)
    assert db_session.scalar(select(Calculation.b)) == 0


# ----- @validates ------------------------------------------------------------


def test_validates_blocks_bad_value_on_loaded_object(db_session):
    user = make_user(db_session)
    calc = add(db_session, user, "Add", 1, 2)

    with pytest.raises(CalculationError, match="a must be a finite number"):
        calc.a = float("inf")
    db_session.commit()

    db_session.expire_all()
    assert db_session.get(Calculation, calc.id).a == 1


# ----- hybrid_property: SQL side --------------------------------------------


EXAMPLES = [
    ("Add", 6, 3),
    ("Sub", 6, -3),
    ("Multiply", 2.5, 4),
    ("Divide", 1, 3),
    ("Add", 0.1, 1e-05),
    ("Divide", -7.25, 0.5),
]


def test_expression_sql_matches_python(db_session):
    user = make_user(db_session)
    for example in EXAMPLES:
        add(db_session, user, *example)
    db_session.expire_all()

    rows = db_session.execute(select(Calculation, Calculation.expression)).all()

    assert len(rows) == len(EXAMPLES)
    for calc, sql_expression in rows:
        assert sql_expression == calc.expression


def test_filter_by_expression(db_session):
    user = make_user(db_session)
    wanted = add(db_session, user, "Add", 6, 3)
    add(db_session, user, "Sub", 6, 3)

    found = db_session.scalars(select(Calculation).where(Calculation.expression == "6 + 3")).all()
    assert [c.id for c in found] == [wanted.id]

    like = db_session.scalars(select(Calculation).where(Calculation.expression.like("% - %")))
    assert [c.type for c in like] == ["Sub"]


def test_order_by_expression(db_session):
    user = make_user(db_session)
    for a in (3, 1, 2):
        add(db_session, user, "Add", a, 1)

    ordered = db_session.scalars(select(Calculation.expression).order_by(Calculation.expression))
    assert list(ordered) == ["1 + 1", "2 + 1", "3 + 1"]


# ----- Composite index ------------------------------------------------------


def test_composite_index_exists(db_session):
    indexes = {
        index["name"]: index["column_names"]
        for index in inspect(db_session.connection()).get_indexes("calculations")
    }
    assert indexes["ix_calculations_user_id_created_at"] == ["user_id", "created_at"]


def test_postgres_can_use_composite_index(db_session):
    user = make_user(db_session)
    add(db_session, user, "Add", 1, 2)
    # The table is tiny, so tell the planner not to prefer a full scan.
    db_session.execute(text("SET LOCAL enable_seqscan = off"))

    plan = db_session.execute(
        text(
            "EXPLAIN SELECT * FROM calculations WHERE user_id = :user_id ORDER BY created_at"
        ),
        {"user_id": user.id},
    ).scalars().all()

    assert "ix_calculations_user_id_created_at" in "\n".join(plan)


# ----- selectinload ---------------------------------------------------------


def test_selectinload_loads_calculations_up_front(db_session):
    user = make_user(db_session)
    for a in (1, 2, 3):
        add(db_session, user, "Multiply", a, 2)
    user_id = user.id
    db_session.expunge_all()

    with count_queries() as statements:
        loaded = get_user_with_calculations(db_session, user_id)
        results = [c.result for c in loaded.calculations]

    # (Sorted because rows made in one test transaction share a created_at.)
    assert sorted(results) == [2, 4, 6]
    # One query for the user, one "WHERE user_id IN (...)" for the calculations,
    # and nothing more when the list is used.
    assert len(statements) == 2
    assert " IN (" in statements[1]


def test_without_selectinload_the_list_is_loaded_lazily(db_session):
    user = make_user(db_session)
    add(db_session, user, "Add", 1, 2)
    user_id = user.id
    db_session.expunge_all()

    loaded = get_user(db_session, user_id)
    assert "calculations" in inspect(loaded).unloaded

    with count_queries() as statements:
        assert len(loaded.calculations) == 1
    assert len(statements) == 1


def test_get_user_with_calculations_unknown_user(db_session):
    assert get_user_with_calculations(db_session, uuid.uuid4()) is None


# ----- column_property: calculation_count ----------------------------------


def test_calculation_count(db_session):
    alice = make_user(db_session, "alice")
    bob = make_user(db_session, "bob")
    assert alice.calculation_count == 0

    for a in (1, 2, 3):
        add(db_session, alice, "Add", a, 1)
    add(db_session, bob, "Add", 1, 1)
    # The count is read when the user is loaded, so reload it.
    db_session.refresh(alice)
    db_session.refresh(bob)

    assert (alice.calculation_count, bob.calculation_count) == (3, 1)


def test_calculation_count_in_queries(db_session):
    alice = make_user(db_session, "alice")
    bob = make_user(db_session, "bob")
    make_user(db_session, "carol")
    for _ in range(2):
        add(db_session, alice, "Add", 1, 1)
    add(db_session, bob, "Add", 1, 1)

    busy = db_session.scalars(select(User.username).where(User.calculation_count > 0))
    assert sorted(busy) == ["alice", "bob"]

    by_count = db_session.scalars(
        select(User.username).order_by(User.calculation_count.desc(), User.username)
    )
    assert list(by_count) == ["alice", "bob", "carol"]


# ----- GET /users/{id}/calculations -----------------------------------------


def test_user_calculations_route(client):
    user = client.post(
        "/users",
        json={"username": "route_user", "email": "route@example.com", "password": "Secret123"},
    ).json()
    for calculation_type in ("Add", "Divide"):
        client.post(
            "/calculations",
            json={"a": 8, "b": 2, "type": calculation_type, "user_id": user["id"]},
        )

    response = client.get(f"/users/{user['id']}/calculations")

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "route_user"
    assert body["calculation_count"] == 2
    assert {c["type"]: c["result"] for c in body["calculations"]} == {"Add": 10, "Divide": 4}
    assert "password_hash" not in body


def test_user_calculations_route_unknown_user(client):
    assert client.get(f"/users/{uuid.uuid4()}/calculations").status_code == 404
