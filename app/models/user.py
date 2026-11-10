"""SQLAlchemy model for a user."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func, select
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.database import Base
from app.models.calculation import Calculation


class User(Base):
    __tablename__ = "users"

    # A random UUID instead of 1, 2, 3...: ids can't be guessed or counted.
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # unique=True creates a UNIQUE constraint in PostgreSQL, so duplicates are
    # rejected by the database itself, not only by application code.
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Only the bcrypt hash is ever stored - never the plain-text password.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Set by the database at insert time, stored with its time zone.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # A user's saved calculations, oldest first. passive_deletes lets the
    # database's ON DELETE CASCADE remove them when the user is deleted.
    calculations: Mapped[list[Calculation]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=(Calculation.created_at, Calculation.id),
    )

    # How many calculations this user has. It isn't a real column: it's a
    # correlated subquery that PostgreSQL runs as part of the SELECT that loads
    # the user, so you get the count without loading the calculations.
    calculation_count: Mapped[int] = column_property(
        select(func.count(Calculation.id))
        .where(Calculation.user_id == id)
        .correlate_except(Calculation)
        .scalar_subquery()
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
