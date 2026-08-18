"""Compose one traceable consultant-year view from existing domain services."""

import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from annual_entitlement import service as entitlement_service
from audit import list_audit_events
from carry_forward import service as carry_forward_service
from consultants import service as consultant_service
from consultants.schemas import ConsultantRead
from job_plans import service as job_plan_service
from job_plans.persistence import JobPlanRecord
from job_plans.schemas import JobPlanRead
from leave_bookings import service as booking_service
from leave_bookings.schemas import (
    ActivityHoursRead,
    BalanceRead,
    LeaveWarningRead,
    PlanningRead,
)
from leave_years import service as leave_year_service
from leave_years.schemas import LeaveYearRead

from .leave_log import leave_log_entries
from .schemas import (
    AuditEventRead,
    BalancePositionRead,
    BalanceViewsRead,
    ConsultantYearSummaryRead,
    JobPlanPeriodSummary,
    WeekdayCountsRead,
)

ZERO = Decimal("0")


def _activity(dcc: Decimal, spa: Decimal, other: Decimal) -> ActivityHoursRead:
    return ActivityHoursRead(
        dcc_hours=dcc,
        spa_hours=spa,
        other_hours=other,
        total_hours=dcc + spa + other,
    )


def _add(left: ActivityHoursRead, right: ActivityHoursRead) -> ActivityHoursRead:
    return _activity(
        left.dcc_hours + right.dcc_hours,
        left.spa_hours + right.spa_hours,
        left.other_hours + right.other_hours,
    )


def _position(balance: BalanceRead | None) -> BalancePositionRead | None:
    if balance is None:
        return None
    return BalancePositionRead(
        available=_add(balance.opening, balance.carry_forward),
        used=_add(balance.public_holidays, balance.bookings),
        remaining=balance.remaining,
    )


def _empty_planning(leave_year_id: int, start_date: date, end_date: date) -> PlanningRead:
    return PlanningRead(
        leave_year_id=leave_year_id,
        start_date=start_date,
        end_date=end_date,
        holidays=(),
        bookings=(),
        projected=None,
        confirmed=None,
        actual=None,
        warnings=(
            LeaveWarningRead(
                code="job-plan.required",
                message="Add a job plan to calculate leave and balances.",
                severity="info",
            ),
        ),
    )


def _split_by_pa(hours: Decimal, plan: JobPlanRecord) -> tuple[Decimal, Decimal]:
    total = plan.dcc_pas + plan.spa_pas + plan.other_pas
    if total == 0:
        return ZERO, ZERO
    dcc = hours * plan.dcc_pas / total
    spa = hours - dcc if plan.other_pas == 0 else hours * plan.spa_pas / total
    return dcc, spa


def _periods(
    plans: tuple[JobPlanRecord, ...],
    total_entitlement: Decimal | None,
    active_start: date,
    active_end: date,
) -> tuple[JobPlanPeriodSummary, ...]:
    if total_entitlement is None:
        total_entitlement = ZERO
    active_days = (active_end - active_start).days + 1
    result: list[JobPlanPeriodSummary] = []

    for plan in plans:
        start = max(plan.effective_from, active_start)
        end = min(plan.effective_until - timedelta(days=1), active_end)
        if end < start:
            continue
        days = (end - start).days + 1
        gross = total_entitlement * Decimal(days) / Decimal(active_days)
        dcc, spa = _split_by_pa(gross, plan)
        result.append(
            JobPlanPeriodSummary(
                job_plan_id=plan.id,
                effective_from=start,
                effective_until=end,
                calendar_days=days,
                contracted_pas=plan.contracted_pas,
                dcc_pas=plan.dcc_pas,
                spa_pas=plan.spa_pas,
                standard_dcc_hours=(
                    sum((day.dcc_hours for day in plan.days), ZERO) / Decimal(plan.week_count)
                ),
                standard_spa_hours=(
                    sum((day.spa_hours for day in plan.days), ZERO) / Decimal(plan.week_count)
                ),
                gross_entitlement_hours=gross,
                dcc_entitlement_hours=dcc,
                spa_entitlement_hours=spa,
            )
        )
    return tuple(result)


def _weekday_counts(planning: PlanningRead) -> WeekdayCountsRead:
    logged_dates = {holiday.holiday_date for holiday in planning.holidays}
    for booking in planning.bookings:
        if booking.state.value != "taken":
            continue
        logged_dates.update(
            day.leave_date for day in booking.days if day.deduction.total_hours > ZERO
        )
    counts = [sum(day.weekday() == weekday for day in logged_dates) for weekday in range(5)]
    return WeekdayCountsRead(
        monday=counts[0],
        tuesday=counts[1],
        wednesday=counts[2],
        thursday=counts[3],
        friday=counts[4],
    )


def get_summary(
    session: Session, consultant_id: int, leave_year_id: int
) -> ConsultantYearSummaryRead:
    consultant = consultant_service.get_consultant(session, consultant_id)
    leave_year = leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    plans = job_plan_service.list_job_plans(session, consultant_id, leave_year_id)
    entitlement = entitlement_service.get_workspace(session, consultant_id, leave_year_id)
    carry_forward = carry_forward_service.get_carry_forward(session, consultant_id, leave_year_id)
    planning = (
        booking_service.planning(session, consultant_id, leave_year_id)
        if plans
        else _empty_planning(
            leave_year.id,
            leave_year.start_date,
            leave_year.end_date,
        )
    )

    recommendation = entitlement.recommendation
    application = entitlement.application
    total_entitlement = None
    allocation_source: Literal["recommendation", "applied"] | None = None
    if recommendation is not None:
        total_entitlement = recommendation.recommended_entitlement.total_hours
        allocation_source = "recommendation"
    elif application is not None:
        total_entitlement = application.entitlement.total_hours
        allocation_source = "applied"

    active_start = max(
        leave_year.start_date,
        leave_year.employment_start or leave_year.start_date,
    )
    active_end = min(
        leave_year.end_date,
        leave_year.employment_end or leave_year.end_date,
    )
    events = list_audit_events(session, consultant_id, limit=50)

    return ConsultantYearSummaryRead(
        consultant=ConsultantRead.model_validate(consultant),
        leave_year=LeaveYearRead.model_validate(leave_year),
        job_plans=tuple(JobPlanRead.model_validate(plan) for plan in plans),
        entitlement=entitlement,
        carry_forward=carry_forward,
        allocation_source=allocation_source,
        job_plan_periods=_periods(plans, total_entitlement, active_start, active_end),
        planning=planning,
        leave_log=leave_log_entries(planning),
        balances=BalanceViewsRead(
            projected=_position(planning.projected),
            confirmed=_position(planning.confirmed),
            actual=_position(planning.actual),
        ),
        weekday_counts=_weekday_counts(planning),
        warnings=planning.warnings,
        audit_events=tuple(
            AuditEventRead(
                id=event.id,
                entity_type=event.entity_type,
                action=event.action,
                recorded_at=event.recorded_at,
                details=json.loads(event.details),
            )
            for event in events
        ),
    )
