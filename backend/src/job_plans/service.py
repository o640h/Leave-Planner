"""Persistence and preview operations for consultant job plans."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from audit import record_audit_event
from domain import ActivityType, Hours, ProgrammedActivities, RuleId
from errors import ApiError
from leave_years import service as leave_year_service
from leave_years.models import LeaveYear
from removal import EntitlementRemovalStatus, RemovalCommand, RemovalImpact, RemovalResult

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
from .versioning import JobPlanHistory, JobPlanVersion


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
        additional_dcc_hours=Hours(details.additional_dcc_hours),
        additional_spa_hours=Hours(details.additional_spa_hours),
        reconciliation_override_reason=reason,
    )


def calculation_history(
    records: tuple[JobPlanRecord, ...],
) -> JobPlanHistory:
    """Adapt stored job plans to the pure calculation engine."""

    versions: list[JobPlanVersion] = []

    for record in records:
        days = tuple(
            JobPlanDay(
                cycle_week=day.cycle_week,
                weekday=Weekday(day.weekday),
                activities=tuple(
                    ActivityAllocation(
                        activity_type=activity_type,
                        hours=Hours(hours),
                    )
                    for activity_type, hours in (
                        (ActivityType.DCC, day.dcc_hours),
                        (ActivityType.SPA, day.spa_hours),
                        (ActivityType.OTHER, day.other_hours),
                    )
                    if hours > 0
                ),
            )
            for day in record.days
        )

        cycle = JobPlanCycle(
            week_count=record.week_count,
            contracted_pas=ProgrammedActivities(record.contracted_pas),
            dcc_pas=ProgrammedActivities(record.dcc_pas),
            spa_pas=ProgrammedActivities(record.spa_pas),
            other_pas=ProgrammedActivities(record.other_pas),
            hours_per_pa=Hours(record.hours_per_pa),
            days=days,
            additional_dcc_hours=Hours(record.additional_dcc_hours),
            additional_spa_hours=Hours(record.additional_spa_hours),
            reconciliation_override_reason=(record.reconciliation_override_reason),
        )

        versions.append(
            JobPlanVersion(
                version_id=RuleId(f"job-plan.{record.id}"),
                effective_from=record.effective_from,
                effective_to=record.effective_until - timedelta(days=1),
                cycle_anchor_date=record.cycle_anchor_date,
                cycle=cycle,
            )
        )

    return JobPlanHistory(tuple(versions))


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
        average_standard_dcc_hours=cycle.average_standard_activity_hours(ActivityType.DCC).value,
        average_standard_spa_hours=cycle.average_standard_activity_hours(ActivityType.SPA).value,
        average_standard_hours=cycle.average_standard_weekly_hours.value,
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
    job_plan.additional_dcc_hours = details.additional_dcc_hours
    job_plan.additional_spa_hours = details.additional_spa_hours
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
        "additional_dcc_hours": format(job_plan.additional_dcc_hours, "f"),
        "additional_spa_hours": format(job_plan.additional_spa_hours, "f"),
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


def _coverage_after_removal(
    leave_year: LeaveYear,
    job_plans: tuple[JobPlanRecord, ...],
    removed_id: int,
) -> bool:
    """Return whether remaining plans cover every active leave-year date."""

    active_start = max(leave_year.start_date, leave_year.employment_start or leave_year.start_date)
    active_end = min(leave_year.end_date, leave_year.employment_end or leave_year.end_date)
    if active_end < active_start:
        return True

    remaining = tuple(plan for plan in job_plans if plan.id != removed_id)
    current = active_start
    while current <= active_end:
        if not any(plan.effective_from <= current < plan.effective_until for plan in remaining):
            return False
        current += timedelta(days=1)
    return True


def removal_impact(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    job_plan_id: int,
) -> RemovalImpact:
    """Explain the coverage and entitlement effect before deleting a plan."""

    from annual_entitlement.service import current_application

    leave_year = leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    job_plan = get_job_plan(session, consultant_id, leave_year_id, job_plan_id)
    plans = list_job_plans(session, consultant_id, leave_year_id)
    complete_coverage = _coverage_after_removal(leave_year, plans, job_plan.id)
    application = current_application(session, leave_year_id)

    consequences = [
        (
            f"The plan covering {job_plan.effective_from:%d %b %Y} to "
            f"{job_plan.effective_until:%d %b %Y} will be deleted."
        ),
        f"{len(plans) - 1} job plan(s) will remain in this leave year.",
    ]
    if not complete_coverage:
        consequences.append(
            "The remaining plans will not cover the complete active leave year. "
            "The existing applied entitlement will be kept and marked for attention."
        )
    elif application is not None:
        consequences.append(
            "The entitlement recommendation will be refreshed from the remaining plans."
        )
    consequences.append("The removal will remain recorded in the consultant audit history.")

    return RemovalImpact(
        resource_name=f"Job Plan {job_plan.id}",
        action="delete",
        confirmation_text="DELETE",
        consequences=tuple(consequences),
    )


def remove_job_plan(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    job_plan_id: int,
    command: RemovalCommand,
) -> RemovalResult:
    """Delete a job plan and refresh a still-calculable entitlement."""

    from annual_entitlement.models import EntitlementMode
    from annual_entitlement.service import current_application, refresh_entitlement

    if command.confirmation.strip() != "DELETE":
        raise ApiError(
            status_code=422,
            code="confirmation_mismatch",
            message="Enter DELETE to confirm removal.",
        )

    leave_year = leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    job_plan = get_job_plan(session, consultant_id, leave_year_id, job_plan_id)
    plans = list_job_plans(session, consultant_id, leave_year_id)
    complete_coverage = _coverage_after_removal(leave_year, plans, job_plan.id)
    before = snapshot(job_plan)

    session.delete(job_plan)
    session.flush()
    record_audit_event(
        session,
        consultant_id=consultant_id,
        entity_type="job_plan",
        entity_id=job_plan_id,
        action="deleted",
        details={"before": before, "complete_coverage_after_removal": complete_coverage},
    )

    application = current_application(session, leave_year_id)
    status: EntitlementRemovalStatus
    if application is None:
        status = "not_configured"
    elif application.mode == EntitlementMode.MANUAL.value:
        status = "preserved"
    elif not complete_coverage:
        status = "needs_attention"
    else:
        try:
            refresh_entitlement(session, consultant_id, leave_year_id)
            status = "refreshed"
        except ApiError:
            status = "needs_attention"

    return RemovalResult(
        message="The job plan was deleted.",
        entitlement_status=status,
    )
