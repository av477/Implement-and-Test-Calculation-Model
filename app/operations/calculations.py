"""Database operations for calculations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculations.factory import compute_result
from app.models import Calculation, User
from app.schemas import CalculationCreate


class UserNotFoundError(Exception):
    """Raised when a calculation refers to a user that doesn't exist."""


def create_calculation(db: Session, calc_in: CalculationCreate) -> Calculation:
    """Compute the result with the factory and save the calculation.

    Raises ``UserNotFoundError`` for an unknown ``user_id`` and
    ``CalculationError`` if the result isn't a valid number.
    """
    if calc_in.user_id is not None and db.get(User, calc_in.user_id) is None:
        raise UserNotFoundError(f"User {calc_in.user_id} not found")

    calculation = Calculation(
        a=calc_in.a,
        b=calc_in.b,
        type=calc_in.type,
        result=compute_result(calc_in.type, calc_in.a, calc_in.b),
        user_id=calc_in.user_id,
    )
    db.add(calculation)
    db.commit()
    db.refresh(calculation)
    return calculation


def get_calculation(db: Session, calculation_id: int) -> Calculation | None:
    return db.get(Calculation, calculation_id)


def list_calculations(db: Session, user_id: int | None = None) -> list[Calculation]:
    """All calculations (oldest first), or only those of one user."""
    query = select(Calculation).order_by(Calculation.id)
    if user_id is not None:
        query = query.where(Calculation.user_id == user_id)
    return list(db.scalars(query))
