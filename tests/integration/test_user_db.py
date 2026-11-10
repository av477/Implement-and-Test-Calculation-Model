"""Model and CRUD behaviour against a real PostgreSQL database."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models import User
from app.operations import users as crud
from app.schemas import UserCreate
from app.auth.security import verify_password

pytestmark = pytest.mark.integration


def new_user(**overrides) -> UserCreate:
    data = {"username": "bob", "email": "bob@example.com", "password": "Secret123"}
    return UserCreate(**{**data, **overrides})


def test_create_user_stores_hash_not_plain_password(db_session):
    user = crud.create_user(db_session, new_user())

    stored = db_session.execute(
        text("SELECT password_hash FROM users WHERE id = :id"), {"id": user.id}
    ).scalar_one()
    assert stored != "Secret123"
    assert verify_password("Secret123", stored)


def test_created_at_is_set_by_database(db_session):
    user = crud.create_user(db_session, new_user())

    assert user.created_at is not None
    assert user.created_at.tzinfo is not None
    assert abs(datetime.now(timezone.utc) - user.created_at) < timedelta(minutes=1)


def test_duplicate_username_is_rejected(db_session):
    crud.create_user(db_session, new_user())

    with pytest.raises(crud.DuplicateUserError):
        crud.create_user(db_session, new_user(email="other@example.com"))


def test_duplicate_email_is_rejected(db_session):
    crud.create_user(db_session, new_user())

    with pytest.raises(crud.DuplicateUserError):
        crud.create_user(db_session, new_user(username="someone_else"))


def test_session_still_usable_after_duplicate(db_session):
    crud.create_user(db_session, new_user())
    with pytest.raises(crud.DuplicateUserError):
        crud.create_user(db_session, new_user())

    crud.create_user(db_session, new_user(username="carol", email="carol@example.com"))
    assert len(db_session.scalars(select(User)).all()) == 2


def test_unique_constraint_enforced_by_database_itself(db_session):
    # Bypass crud/schemas entirely: the table's UNIQUE constraint must still hold.
    db_session.add(User(username="dave", email="dave@example.com", password_hash="x"))
    db_session.flush()
    db_session.add(User(username="dave", email="dave2@example.com", password_hash="x"))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_authenticate_user(db_session):
    crud.create_user(db_session, new_user())

    assert crud.authenticate_user(db_session, "bob", "Secret123") is not None
    assert crud.authenticate_user(db_session, "BOB@example.com", "Secret123") is not None
    assert crud.authenticate_user(db_session, "bob", "wrong-Pass1") is None
    assert crud.authenticate_user(db_session, "nobody", "Secret123") is None
