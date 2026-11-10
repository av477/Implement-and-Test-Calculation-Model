"""Database operations for calculations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Calculation, User
from app.schemas import CalculationCreate, CalculationUpdate


class UserNotFoundError(Exception):
    """Raised when a calculation refers to a user that doesn't exist."""


def create_calculation(db: Session, calc_in: CalculationCreate) -> Calculation:
    """Use the factory to build the right subclass, then save it.

    Raises ``UserNotFoundError`` for an unknown ``user_id`` and
    ``CalculationError`` if the result isn't a valid number.
    """
    if db.get(User, calc_in.user_id) is None:
        raise UserNotFoundError(f"User {calc_in.user_id} not found")

    calculation = Calculation.create(calc_in.type, calc_in.a, calc_in.b, calc_in.user_id)
    db.add(calculation)
    db.commit()
    db.refresh(calculation)
    return calculation


def get_calculation(db: Session, calculation_id: UUID) -> Calculation | None:
    return db.get(Calculation, calculation_id)


def list_calculations(db: Session, user_id: UUID | None = None) -> list[Calculation]:
    """All calculations (oldest first), or only those of one user."""
    query = select(Calculation).order_by(Calculation.created_at, Calculation.id)
    if user_id is not None:
        query = query.where(Calculation.user_id == user_id)
    return list(db.scalars(query))


def update_calculation(
    db: Session, calculation: Calculation, changes: CalculationUpdate
) -> Calculation:
    """Change ``a`` and/or ``b`` and recompute the result with the same subclass.

    The new result is computed before anything is changed, so a failure
    (for example dividing by zero) leaves the stored calculation as it was.
    """
    a = calculation.a if changes.a is None else changes.a
    b = calculation.b if changes.b is None else changes.b
    result = calculation.compute(a, b)

    calculation.a, calculation.b, calculation.result = a, b, result
    db.commit()
    db.refresh(calculation)
    return calculation
