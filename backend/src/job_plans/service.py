"""Persistence and preview operations for consultant job plans."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from audit import record_audit_event
from domain import ActivityType, Hours, ProgrammedActivities
from errors import ApiError
from leave_years import service as leave_year_service
from leave_years.models import LeaveYear

from .models import (
    ActivityAllocation,
    JobPlanCycle,
    JobPlanDay,
    Weekday,
)
from .persistence import JobPlanDayRecord, JobPlanRecord
from .schemas import (
    JobPlanCreate,
    JobPlanDayFields,
    JobPlanFields,
    JobPlanPreview,
    JobPlanUpdate,
)


def monday_on_or_before(value: date) -> date:
    """Return the Monday that anchors the date's cycle week."""

    return value - timedelta(days=value.weekday())


def list_job_plans(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
) -> tuple[JobPlanRecord, ...]:
    leave_year_service.get_leave_year(
        session,
        consultant_id,
        leave_year_id,
    )

    statement = (
        select(JobPlanRecord)
        .options(selectinload(JobPlanRecord.days))
        .where(JobPlanRecord.leave_year_id == leave_year_id)
        .order_by(JobPlanRecord.effective_from, JobPlanRecord.id)
    )
    return tuple(session.scalars(statement))


def get_job_plan(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    job_plan_id: int,
) -> JobPlanRecord:
    leave_year_service.get_leave_year(
        session,
        consultant_id,
        leave_year_id,
    )

    statement = (
        select(JobPlanRecord)
        .options(selectinload(JobPlanRecord.days))
        .where(
            JobPlanRecord.id == job_plan_id,
            JobPlanRecord.leave_year_id == leave_year_id,
        )
    )
    job_plan = session.scalar(statement)

    if job_plan is None:
        raise ApiError(
            status_code=404,
            code="job_plan_not_found",
            message="The requested job plan could not be found.",
        )

    return job_plan


def validate_effective_dates(
    leave_year: LeaveYear,
    details: JobPlanFields,
) -> None:
    """Keep the exclusive job-plan period inside the leave year."""

    leave_year_until = leave_year.end_date + timedelta(days=1)

    if details.effective_from < leave_year.start_date or details.effective_until > leave_year_until:
        raise ApiError(
            status_code=422,
            code="job_plan_outside_leave_year",
            message="The job plan must fall inside the selected leave year.",
        )


def prevent_overlap(
    session: Session,
    *,
    leave_year_id: int,
    effective_from: date,
    effective_until: date,
    excluding_id: int | None = None,
) -> None:
    """Reject intersecting half-open effective periods."""

    statement = select(JobPlanRecord.id).where(
        JobPlanRecord.leave_year_id == leave_year_id,
        JobPlanRecord.effective_from < effective_until,
        JobPlanRecord.effective_until > effective_from,
    )

    if excluding_id is not None:
        statement = statement.where(JobPlanRecord.id != excluding_id)

    if session.scalar(statement) is not None:
        raise ApiError(
            status_code=409,
            code="job_plan_overlap",
            message="This job plan overlaps another plan in the leave year.",
        )


def activity_allocations(
    details: JobPlanDayFields,
) -> tuple[ActivityAllocation, ...]:
    """Convert one API weekday into non-zero calculation activities."""

    values = (
        (ActivityType.DCC, details.dcc_hours),
        (ActivityType.SPA, details.spa_hours),
        (ActivityType.OTHER, details.other_hours),
    )

    return tuple(
        ActivityAllocation(
            activity_type=activity_type,
            hours=Hours(hours),
        )
        for activity_type, hours in values
        if hours > 0
    )


def calculation_cycle(
    details: JobPlanFields,
    *,
    preview: bool = False,
) -> JobPlanCycle:
    """Adapt API fields to the existing pure calculation model."""

    allocated_pas = details.dcc_pas + details.spa_pas + details.other_pas

    reason = details.reconciliation_override_reason
    if preview and allocated_pas != details.contracted_pas and reason is None:
        reason = "Preview only"

    days = tuple(
        JobPlanDay(
            cycle_week=day.cycle_week,
            weekday=Weekday(day.weekday),
            activities=activity_allocations(day),
        )
        for day in sorted(
            details.days,
            key=lambda item: (item.cycle_week, item.weekday),
        )
    )

    return JobPlanCycle(
        week_count=details.week_count,
        contracted_pas=ProgrammedActivities(details.contracted_pas),
        dcc_pas=ProgrammedActivities(details.dcc_pas),
        spa_pas=ProgrammedActivities(details.spa_pas),
        other_pas=ProgrammedActivities(details.other_pas),
        hours_per_pa=Hours(details.hours_per_pa),
        days=days,
        reconciliation_override_reason=reason,
    )


def preview_job_plan(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    details: JobPlanFields,
) -> JobPlanPreview:
    """Return reconciliation and visible-hours information without saving."""

    leave_year = leave_year_service.get_leave_year(
        session,
        consultant_id,
        leave_year_id,
    )
    validate_effective_dates(leave_year, details)

    cycle = calculation_cycle(details, preview=True)
    divisor = Decimal(cycle.week_count)

    warning = None
    if not cycle.is_reconciled:
        warning = (
            "Allocated activity PAs differ from total contracted PAs. "
            "Enter an override reason before saving."
        )

    return JobPlanPreview(
        **details.model_dump(),
        allocated_pas=cycle.allocated_pas.value,
        reconciliation_variance=cycle.reconciliation_variance,
        is_reconciled=cycle.is_reconciled,
        average_visible_hours=cycle.average_weekly_hours.value,
        average_dcc_hours=(cycle.activity_hours(ActivityType.DCC).value / divisor),
        average_spa_hours=(cycle.activity_hours(ActivityType.SPA).value / divisor),
        average_other_hours=(cycle.activity_hours(ActivityType.OTHER).value / divisor),
        scheduled_average_pas=cycle.scheduled_average_weekly_pas.value,
        warning=warning,
    )


def day_record(details: JobPlanDayFields) -> JobPlanDayRecord:
    return JobPlanDayRecord(
        cycle_week=details.cycle_week,
        weekday=details.weekday,
        dcc_hours=details.dcc_hours,
        spa_hours=details.spa_hours,
        other_hours=details.other_hours,
    )


def assign_fields(
    job_plan: JobPlanRecord,
    details: JobPlanFields,
) -> None:
    """Copy validated API fields into a stored job plan."""

    job_plan.effective_from = details.effective_from
    job_plan.effective_until = details.effective_until
    job_plan.cycle_anchor_date = details.cycle_anchor_date or monday_on_or_before(
        details.effective_from
    )
    job_plan.week_count = details.week_count

    job_plan.contracted_pas = details.contracted_pas
    job_plan.dcc_pas = details.dcc_pas
    job_plan.spa_pas = details.spa_pas
    job_plan.other_pas = details.other_pas
    job_plan.hours_per_pa = details.hours_per_pa
    job_plan.reconciliation_override_reason = details.reconciliation_override_reason

    job_plan.days.extend(day_record(day) for day in details.days)


def snapshot(job_plan: JobPlanRecord) -> dict[str, object]:
    """Create JSON-safe audit information."""

    return {
        "effective_from": job_plan.effective_from.isoformat(),
        "effective_until": job_plan.effective_until.isoformat(),
        "cycle_anchor_date": job_plan.cycle_anchor_date.isoformat(),
        "week_count": job_plan.week_count,
        "contracted_pas": format(job_plan.contracted_pas, "f"),
        "dcc_pas": format(job_plan.dcc_pas, "f"),
        "spa_pas": format(job_plan.spa_pas, "f"),
        "other_pas": format(job_plan.other_pas, "f"),
        "hours_per_pa": format(job_plan.hours_per_pa, "f"),
        "reconciliation_override_reason": (job_plan.reconciliation_override_reason),
        "days": [
            {
                "cycle_week": day.cycle_week,
                "weekday": day.weekday,
                "dcc_hours": format(day.dcc_hours, "f"),
                "spa_hours": format(day.spa_hours, "f"),
                "other_hours": format(day.other_hours, "f"),
            }
            for day in job_plan.days
        ],
    }


def create_job_plan(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    details: JobPlanCreate,
) -> JobPlanRecord:
    leave_year = leave_year_service.get_leave_year(
        session,
        consultant_id,
        leave_year_id,
    )
    validate_effective_dates(leave_year, details)
    prevent_overlap(
        session,
        leave_year_id=leave_year_id,
        effective_from=details.effective_from,
        effective_until=details.effective_until,
    )

    job_plan = JobPlanRecord(leave_year_id=leave_year_id)
    assign_fields(job_plan, details)

    session.add(job_plan)
    session.flush()

    record_audit_event(
        session,
        consultant_id=consultant_id,
        entity_type="job_plan",
        entity_id=job_plan.id,
        action="created",
        details={"after": snapshot(job_plan)},
    )

    return job_plan


def update_job_plan(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    job_plan_id: int,
    details: JobPlanUpdate,
) -> JobPlanRecord:
    leave_year = leave_year_service.get_leave_year(
        session,
        consultant_id,
        leave_year_id,
    )
    job_plan = get_job_plan(
        session,
        consultant_id,
        leave_year_id,
        job_plan_id,
    )

    validate_effective_dates(leave_year, details)
    prevent_overlap(
        session,
        leave_year_id=leave_year_id,
        effective_from=details.effective_from,
        effective_until=details.effective_until,
        excluding_id=job_plan.id,
    )

    before = snapshot(job_plan)

    job_plan.days.clear()
    session.flush()
    assign_fields(job_plan, details)
    session.flush()

    record_audit_event(
        session,
        consultant_id=consultant_id,
        entity_type="job_plan",
        entity_id=job_plan.id,
        action="updated",
        details={
            "before": before,
            "after": snapshot(job_plan),
        },
    )

    return job_plan
