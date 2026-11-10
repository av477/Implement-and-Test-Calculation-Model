"""Database operations for users."""

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.security import hash_password, verify_password
from app.models import User
from app.schemas import UserCreate


class DuplicateUserError(Exception):
    """Raised when the username or email is already registered."""


def create_user(db: Session, user_in: UserCreate) -> User:
    """Hash the password and insert a new user. Raises DuplicateUserError on conflict."""
    user = User(
        username=user_in.username,
        email=user_in.email,
        password_hash=hash_password(user_in.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        # The UNIQUE constraints on the table are the source of truth, which
        # also covers two requests racing to register the same name.
        db.rollback()
        raise DuplicateUserError("Username or email already registered") from exc
    db.refresh(user)
    return user


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_user_by_login(db: Session, login: str) -> User | None:
    """Find a user by username or email (case-insensitive, both are stored lowercase)."""
    login = login.strip().lower()
    return db.scalar(select(User).where(or_(User.username == login, User.email == login)))


def authenticate_user(db: Session, login: str, password: str) -> User | None:
    """Return the user if the password matches, otherwise None."""
    user = get_user_by_login(db, login)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user
