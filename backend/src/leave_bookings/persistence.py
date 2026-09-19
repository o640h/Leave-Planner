"""SQLite records for leave bookings and their calculated days."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class LeaveBookingRecord(Base):
    """One operator-entered period of leave."""

    __tablename__ = "leave_bookings"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_leave_booking_dates"),
        CheckConstraint(
            "state IN ('requested', 'approved', 'cancelled')",
            name="ck_leave_booking_state",
        ),
        CheckConstraint(
            "cancellation_requested_at IS NULL OR state = 'approved'",
            name="ck_leave_booking_cancellation_request",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    leave_year_id: Mapped[int] = mapped_column(
        ForeignKey("leave_years.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requested_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    cancellation_requested_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    days: Mapped[list[LeaveBookingDayRecord]] = relationship(
        back_populates="booking",
        cascade="all, delete-orphan",
        order_by="LeaveBookingDayRecord.leave_date",
    )


class LeaveBookingDayRecord(Base):
    """Calculated deduction snapshot for one date in a booking."""

    __tablename__ = "leave_booking_days"
    __table_args__ = (
        UniqueConstraint("booking_id", "leave_date", name="uq_leave_booking_day_date"),
        CheckConstraint(
            "standard_dcc_hours >= 0 AND standard_spa_hours >= 0 AND standard_other_hours >= 0",
            name="ck_leave_booking_day_standard_hours",
        ),
        CheckConstraint(
            "deduction_dcc_hours >= 0 AND deduction_spa_hours >= 0 AND deduction_other_hours >= 0",
            name="ck_leave_booking_day_deduction_hours",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("leave_bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_plan_versions.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    leave_date: Mapped[date] = mapped_column(Date, nullable=False)
    contracted_pas: Mapped[Decimal | None] = mapped_column(Numeric(9, 3), nullable=True)
    deduction_factor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    standard_dcc_hours: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    standard_spa_hours: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    standard_other_hours: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    deduction_dcc_hours: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    deduction_spa_hours: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    deduction_other_hours: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    override_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    booking: Mapped[LeaveBookingRecord] = relationship(back_populates="days")
