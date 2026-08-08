"""Persisted consultant leave years."""

from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class LeaveYear(Base):
    """One inclusive annual-leave period belonging to a consultant."""

    __tablename__ = "leave_years"
    __table_args__ = (
        CheckConstraint(
            "end_date >= start_date",
            name="ck_leave_year_dates",
        ),
        CheckConstraint(
            """
            employment_start IS NULL
            OR (
                employment_start >= start_date
                AND employment_start <= end_date
            )
            """,
            name="ck_leave_year_employment_start",
        ),
        CheckConstraint(
            """
            employment_end IS NULL
            OR (
                employment_end >= start_date
                AND employment_end <= end_date
            )
            """,
            name="ck_leave_year_employment_end",
        ),
        CheckConstraint(
            """
            employment_start IS NULL
            OR employment_end IS NULL
            OR employment_end >= employment_start
            """,
            name="ck_leave_year_employment_dates",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    consultant_id: Mapped[int] = mapped_column(
        ForeignKey("consultants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    employment_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    employment_end: Mapped[date | None] = mapped_column(Date, nullable=True)
