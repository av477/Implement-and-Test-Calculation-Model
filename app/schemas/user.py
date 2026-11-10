"""Pydantic schemas: what the API accepts and what it returns."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.auth.security import BCRYPT_MAX_BYTES

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]+$"


class UserCreate(BaseModel):
    """Data required to register a new user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.lower()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("password")
    @classmethod
    def check_password_strength(cls, value: str) -> str:
        if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
            raise ValueError(f"password must be at most {BCRYPT_MAX_BYTES} bytes")
        missing = [
            label
            for label, pattern in (
                ("an uppercase letter", r"[A-Z]"),
                ("a lowercase letter", r"[a-z]"),
                ("a digit", r"\d"),
            )
            if not re.search(pattern, value)
        ]
        if missing:
            raise ValueError("password must contain " + ", ".join(missing))
        return value


class UserRead(BaseModel):
    """User details returned by the API. ``password_hash`` is deliberately absent."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    created_at: datetime


class UserLogin(BaseModel):
    """Credentials for checking a password against the stored hash."""

    username: str
    password: str
