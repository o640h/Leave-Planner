"""Persistence for shared calendars and consultant-year holiday treatments."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class HolidayCalendarVersionRecord(Base):
    __tablename__ = "holiday_calendar_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    source_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.current_timestamp(), nullable=False
    )
    events: Mapped[list[HolidayCalendarEventRecord]] = relationship(
        back_populates="calendar",
        cascade="all, delete-orphan",
        order_by="HolidayCalendarEventRecord.holiday_date",
    )


class HolidayCalendarEventRecord(Base):
    __tablename__ = "holiday_calendar_events"
    __table_args__ = (
        UniqueConstraint(
            "calendar_version_id", "holiday_date", name="uq_holiday_calendar_event_date"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calendar_version_id: Mapped[int] = mapped_column(
        ForeignKey("holiday_calendar_versions.id", ondelete="CASCADE"), nullable=False
    )
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    notes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    calendar: Mapped[HolidayCalendarVersionRecord] = relationship(back_populates="events")


class HolidayCorrectionRecord(Base):
    __tablename__ = "holiday_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    replacement_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.current_timestamp(), nullable=False
    )


class PublicHolidayTreatmentRecord(Base):
    __tablename__ = "public_holiday_treatments"
    __table_args__ = (
        UniqueConstraint("leave_year_id", "holiday_date", name="uq_public_holiday_treatment_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    leave_year_id: Mapped[int] = mapped_column(
        ForeignKey("leave_years.id", ondelete="CASCADE"), nullable=False, index=True
    )
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    basis: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
