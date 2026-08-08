"""SQLite models for effective-dated job plans."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class JobPlanRecord(Base):
    """One effective job-plan version belonging to a leave year."""

    __tablename__ = "job_plan_versions"
    __table_args__ = (
        CheckConstraint(
            "effective_until > effective_from",
            name="ck_job_plan_effective_dates",
        ),
        CheckConstraint(
            "cycle_anchor_date <= effective_from",
            name="ck_job_plan_anchor_date",
        ),
        CheckConstraint("week_count >= 1", name="ck_job_plan_week_count"),
        CheckConstraint(
            "contracted_pas >= 0",
            name="ck_job_plan_contracted_pas",
        ),
        CheckConstraint("dcc_pas >= 0", name="ck_job_plan_dcc_pas"),
        CheckConstraint("spa_pas >= 0", name="ck_job_plan_spa_pas"),
        CheckConstraint("other_pas >= 0", name="ck_job_plan_other_pas"),
        CheckConstraint(
            "hours_per_pa > 0",
            name="ck_job_plan_hours_per_pa",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    leave_year_id: Mapped[int] = mapped_column(
        ForeignKey("leave_years.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[date] = mapped_column(Date, nullable=False)
    cycle_anchor_date: Mapped[date] = mapped_column(Date, nullable=False)
    week_count: Mapped[int] = mapped_column(Integer, nullable=False)

    contracted_pas: Mapped[Decimal] = mapped_column(Numeric(9, 3), nullable=False)
    dcc_pas: Mapped[Decimal] = mapped_column(Numeric(9, 3), nullable=False)
    spa_pas: Mapped[Decimal] = mapped_column(Numeric(9, 3), nullable=False)
    other_pas: Mapped[Decimal] = mapped_column(Numeric(9, 3), nullable=False)
    hours_per_pa: Mapped[Decimal] = mapped_column(Numeric(9, 3), nullable=False)

    reconciliation_override_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    days: Mapped[list[JobPlanDayRecord]] = relationship(
        back_populates="job_plan",
        cascade="all, delete-orphan",
        order_by="JobPlanDayRecord.cycle_week, JobPlanDayRecord.weekday",
    )


class JobPlanDayRecord(Base):
    """Visible DCC, SPA, and Other hours for one cycle weekday."""

    __tablename__ = "job_plan_days"
    __table_args__ = (
        CheckConstraint(
            "cycle_week >= 1",
            name="ck_job_plan_day_cycle_week",
        ),
        CheckConstraint(
            "weekday >= 0 AND weekday <= 6",
            name="ck_job_plan_day_weekday",
        ),
        CheckConstraint(
            "dcc_hours >= 0",
            name="ck_job_plan_day_dcc_hours",
        ),
        CheckConstraint(
            "spa_hours >= 0",
            name="ck_job_plan_day_spa_hours",
        ),
        CheckConstraint(
            "other_hours >= 0",
            name="ck_job_plan_day_other_hours",
        ),
        UniqueConstraint(
            "job_plan_id",
            "cycle_week",
            "weekday",
            name="uq_job_plan_day_position",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_plan_id: Mapped[int] = mapped_column(
        ForeignKey("job_plan_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    cycle_week: Mapped[int] = mapped_column(Integer, nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    dcc_hours: Mapped[Decimal] = mapped_column(Numeric(9, 3), nullable=False)
    spa_hours: Mapped[Decimal] = mapped_column(Numeric(9, 3), nullable=False)
    other_hours: Mapped[Decimal] = mapped_column(Numeric(9, 3), nullable=False)

    job_plan: Mapped[JobPlanRecord] = relationship(back_populates="days")
