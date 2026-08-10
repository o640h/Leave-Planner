"""SQLite model for consultant-year carry-forward."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class CarryForwardRecord(Base):
    """Carry-forward stored in the existing compatible adjustment table."""

    __tablename__ = "leave_year_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    leave_year_id: Mapped[int] = mapped_column(
        ForeignKey("leave_years.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    dcc_hours: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    spa_hours: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    other_hours: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.current_timestamp(), nullable=False
    )
