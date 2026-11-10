"""Polymorphic SQLAlchemy models for calculations.

All four kinds of calculation live in ONE table, ``calculations``
(single-table inheritance). The ``type`` column says which kind each row is:

    type = "Add"       ->  Addition
    type = "Sub"       ->  Subtraction
    type = "Multiply"  ->  Multiplication
    type = "Divide"    ->  Division

Because ``type`` is the ``polymorphic_on`` (discriminator) column, SQLAlchemy
reads it when loading a row and builds the matching subclass automatically.
So ``db.get(Calculation, some_id)`` returns, for example, a ``Division``
object, and calling ``.compute()`` on it runs the division logic.

``Calculation.create(type, a, b, user_id)`` is the factory: it picks the right
subclass for a type and fills in the result.
"""

import math
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    case,
    cast,
    func,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.calculations.types import CalculationError, CalculationType
from app.database import Base

if TYPE_CHECKING:  # pragma: no cover - only for type checkers
    from app.models.user import User

_ALLOWED_TYPES = ", ".join(f"'{member.value}'" for member in CalculationType)

# The symbol shown for each type in ``Calculation.expression``.
SYMBOLS = {
    CalculationType.ADD.value: "+",
    CalculationType.SUB.value: "-",
    CalculationType.MULTIPLY.value: "*",
    CalculationType.DIVIDE.value: "/",
}


def _format_number(value: float) -> str:
    """Write a number the way PostgreSQL's float-to-text cast does: 6.0 -> "6",
    2.5 -> "2.5". (The two differ only for whole numbers from 1e15 to 1e16.)"""
    text = repr(float(value))
    return text[:-2] if text.endswith(".0") else text


class Calculation(Base):
    """Base class: the shared columns, the factory and the safety checks."""

    __tablename__ = "calculations"
    # The database itself rejects any type that has no subclass.
    __table_args__ = (
        CheckConstraint(f"type IN ({_ALLOWED_TYPES})", name="ck_calculations_type"),
        # A second guard behind Pydantic: the database refuses to store a
        # division by zero even if someone inserts it with raw SQL.
        CheckConstraint(
            "NOT (type = 'Divide' AND b = 0)", name="ck_calculations_no_zero_divisor"
        ),
        # Speeds up "this user's calculations, oldest first": PostgreSQL can
        # find the user's rows and read them already in created_at order.
        Index("ix_calculations_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Every calculation belongs to a user. The foreign key makes PostgreSQL
    # reject a user_id that doesn't exist, and deleting a user deletes their
    # calculations.
    # (No separate index on user_id: the composite index above starts with
    # user_id, so it already covers lookups by user.)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    a: Mapped[float] = mapped_column(Float, nullable=False)
    b: Mapped[float] = mapped_column(Float, nullable=False)
    # The result is computed when the calculation is created (or its numbers
    # are changed) and stored, so reading it never redoes the math.
    result: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Set by the database on insert, and refreshed by SQLAlchemy on every update.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="calculations")

    __mapper_args__ = {"polymorphic_on": "type"}

    # ----- ORM-level validation -------------------------------------------

    @validates("a", "b")
    def _validate_number(self, key: str, value: float) -> float:
        """Second layer behind Pydantic: runs whenever ``a`` or ``b`` is set
        on the object, so code that skips the schemas can't store bad numbers."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CalculationError(f"{key} must be a number")
        if not math.isfinite(value):
            raise CalculationError(f"{key} must be a finite number")
        return float(value)

    # ----- Hybrid property ------------------------------------------------

    @hybrid_property
    def expression(self) -> str:
        """The calculation as text, e.g. "6 + 3".

        On an object this runs as Python. In a query (``Calculation.expression``)
        it becomes SQL, so you can filter or sort by it in the database.
        """
        return f"{_format_number(self.a)} {SYMBOLS[self.type]} {_format_number(self.b)}"

    @expression.inplace.expression
    @classmethod
    def _expression_sql(cls):
        symbol = case(SYMBOLS, value=cls.type)
        return cast(cls.a, Text) + " " + symbol + " " + cast(cls.b, Text)

    # ----- Factory -------------------------------------------------------

    @classmethod
    # The return annotation is a string because inside this class body the
    # name ``type`` means the column above, not Python's built-in type().
    def subclass_for(cls, calculation_type: CalculationType | str) -> "type[Calculation]":
        """Return the subclass registered for ``calculation_type``."""
        try:
            identity = CalculationType(calculation_type).value
            return cls.__mapper__.polymorphic_map[identity].class_
        except (KeyError, ValueError) as exc:
            raise CalculationError(f"Unsupported calculation type: {calculation_type!r}") from exc

    @classmethod
    def create(
        cls,
        calculation_type: CalculationType | str,
        a: float,
        b: float,
        user_id: uuid.UUID | None = None,
    ) -> "Calculation":
        """Factory: build the right subclass with its result already computed.

        The object is not saved; add it to a session to store it.
        """
        calculation = cls.subclass_for(calculation_type)(a=a, b=b, user_id=user_id)
        calculation.result = calculation.compute(a, b)
        return calculation

    # ----- Math ----------------------------------------------------------

    def _apply(self, a: float, b: float) -> float:
        """Each subclass returns its own raw result here."""
        raise NotImplementedError("Use a Calculation subclass such as Addition")

    def compute(self, a: float, b: float) -> float:
        """Run this type's math on ``a`` and ``b``, rejecting non-finite results."""
        try:
            result = self._apply(a, b)
        except OverflowError as exc:
            raise CalculationError("Result is too large to store") from exc
        if not math.isfinite(result):
            raise CalculationError("Result is too large to store")
        return result

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.id} {self.expression} = {self.result}>"


class Addition(Calculation):
    __mapper_args__ = {"polymorphic_identity": CalculationType.ADD.value}

    def _apply(self, a: float, b: float) -> float:
        return a + b


class Subtraction(Calculation):
    __mapper_args__ = {"polymorphic_identity": CalculationType.SUB.value}

    def _apply(self, a: float, b: float) -> float:
        return a - b


class Multiplication(Calculation):
    __mapper_args__ = {"polymorphic_identity": CalculationType.MULTIPLY.value}

    def _apply(self, a: float, b: float) -> float:
        return a * b


class Division(Calculation):
    __mapper_args__ = {"polymorphic_identity": CalculationType.DIVIDE.value}

    def _apply(self, a: float, b: float) -> float:
        if b == 0:
            raise CalculationError("Cannot divide by zero")
        return a / b
