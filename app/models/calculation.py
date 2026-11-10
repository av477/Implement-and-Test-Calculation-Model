"""SQLAlchemy model for a stored calculation."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.calculations.factory import CalculationType

if TYPE_CHECKING:  # pragma: no cover - only for type checkers
    from app.models.user import User


class Calculation(Base):
    __tablename__ = "calculations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    a: Mapped[float] = mapped_column(Float, nullable=False)
    b: Mapped[float] = mapped_column(Float, nullable=False)
    # Stored as text ("Add", "Sub", ...). create_constraint adds a CHECK
    # constraint, so the database itself rejects any other value.
    type: Mapped[CalculationType] = mapped_column(
        Enum(
            CalculationType,
            name="calculation_type",
            native_enum=False,
            create_constraint=True,
            length=10,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    # The result is computed once, when the calculation is created, and stored.
    # The inputs never change, so the stored value can't go out of date.
    result: Mapped[float] = mapped_column(Float, nullable=False)
    # Optional owner. The foreign key makes PostgreSQL reject a user_id that
    # doesn't exist, and deleting a user deletes their calculations.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User | None"] = relationship(back_populates="calculations")

    def __repr__(self) -> str:
        return f"<Calculation id={self.id} {self.a} {self.type.value} {self.b} = {self.result}>"
