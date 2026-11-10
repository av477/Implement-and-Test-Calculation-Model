import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas import UserCreate, UserRead

pytestmark = pytest.mark.unit

VALID = {"username": "alice_01", "email": "alice@example.com", "password": "Secret123"}


def make(**overrides):
    return UserCreate(**{**VALID, **overrides})


def test_valid_user_create():
    user = make()
    assert user.username == "alice_01"
    assert user.email == "alice@example.com"


def test_username_and_email_are_normalized():
    user = make(username="  Alice_01 ", email="Alice@Example.COM")
    assert user.username == "alice_01"
    assert user.email == "alice@example.com"


@pytest.mark.parametrize("email", ["not-an-email", "alice@", "@example.com", "alice example.com"])
def test_invalid_email_is_rejected(email):
    with pytest.raises(ValidationError) as exc_info:
        make(email=email)
    assert exc_info.value.errors()[0]["loc"] == ("email",)


@pytest.mark.parametrize("username", ["ab", "a" * 51, "has space", "bad!char"])
def test_invalid_username_is_rejected(username):
    with pytest.raises(ValidationError):
        make(username=username)


@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("Short1", "at least 8 characters"),
        ("alllowercase1", "uppercase"),
        ("ALLUPPERCASE1", "lowercase"),
        ("NoDigitsHere", "digit"),
        ("Aa1" + "x" * 70, "72 bytes"),
    ],
)
def test_weak_password_is_rejected(password, message):
    with pytest.raises(ValidationError, match=message):
        make(password=password)


@pytest.mark.parametrize("missing", ["username", "email", "password"])
def test_missing_field_is_rejected(missing):
    data = {k: v for k, v in VALID.items() if k != missing}
    with pytest.raises(ValidationError):
        UserCreate(**data)


def test_user_read_omits_password_hash():
    orm_like = SimpleNamespace(
        id=uuid.uuid4(),
        username="alice_01",
        email="alice@example.com",
        password_hash="$2b$12$secret",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    data = UserRead.model_validate(orm_like).model_dump()
    assert "password_hash" not in data
    assert "password" not in data
    assert set(data) == {"id", "username", "email", "created_at"}
