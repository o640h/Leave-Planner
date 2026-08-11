"""Database operations for consultant leave years."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from audit import record_audit_event
from consultants import service as consultant_service
from errors import ApiError
from removal import RemovalCommand, RemovalImpact, RemovalResult

from .models import LeaveYear
from .schemas import LeaveYearCreate, LeaveYearUpdate


def list_leave_years(
    session: Session,
    consultant_id: int,
) -> tuple[LeaveYear, ...]:
    consultant_service.get_consultant(session, consultant_id)

    statement = (
        select(LeaveYear)
        .where(LeaveYear.consultant_id == consultant_id)
        .order_by(LeaveYear.start_date.desc(), LeaveYear.id.desc())
    )
    return tuple(session.scalars(statement))


def get_leave_year(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
) -> LeaveYear:
    leave_year = session.get(LeaveYear, leave_year_id)

    if leave_year is None or leave_year.consultant_id != consultant_id:
        raise ApiError(
            status_code=404,
            code="leave_year_not_found",
            message="The requested leave year could not be found.",
        )

    return leave_year


def _prevent_overlap(
    session: Session,
    *,
    consultant_id: int,
    start_date: date,
    end_date: date,
    excluding_id: int | None = None,
) -> None:
    statement = select(LeaveYear.id).where(
        LeaveYear.consultant_id == consultant_id,
        LeaveYear.start_date <= end_date,
        LeaveYear.end_date >= start_date,
    )

    if excluding_id is not None:
        statement = statement.where(LeaveYear.id != excluding_id)

    if session.scalar(statement) is not None:
        raise ApiError(
            status_code=409,
            code="leave_year_overlap",
            message="This leave year overlaps another year for the consultant.",
        )


def _snapshot(leave_year: LeaveYear) -> dict[str, object]:
    return {
        "start_date": leave_year.start_date.isoformat(),
        "end_date": leave_year.end_date.isoformat(),
        "employment_start": (
            leave_year.employment_start.isoformat() if leave_year.employment_start else None
        ),
        "employment_end": (
            leave_year.employment_end.isoformat() if leave_year.employment_end else None
        ),
    }


def create_leave_year(
    session: Session,
    consultant_id: int,
    details: LeaveYearCreate,
) -> LeaveYear:
    consultant_service.get_consultant(session, consultant_id)
    _prevent_overlap(
        session,
        consultant_id=consultant_id,
        start_date=details.start_date,
        end_date=details.end_date,
    )

    leave_year = LeaveYear(
        consultant_id=consultant_id,
        **details.model_dump(),
    )
    session.add(leave_year)
    session.flush()

    record_audit_event(
        session,
        consultant_id=consultant_id,
        entity_type="leave_year",
        entity_id=leave_year.id,
        action="created",
        details={"after": _snapshot(leave_year)},
    )

    session.refresh(leave_year)
    return leave_year


def update_leave_year(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    details: LeaveYearUpdate,
) -> LeaveYear:
    leave_year = get_leave_year(session, consultant_id, leave_year_id)
    _prevent_overlap(
        session,
        consultant_id=consultant_id,
        start_date=details.start_date,
        end_date=details.end_date,
        excluding_id=leave_year.id,
    )

    before = _snapshot(leave_year)

    leave_year.start_date = details.start_date
    leave_year.end_date = details.end_date
    leave_year.employment_start = details.employment_start
    leave_year.employment_end = details.employment_end
    session.flush()

    record_audit_event(
        session,
        consultant_id=consultant_id,
        entity_type="leave_year",
        entity_id=leave_year.id,
        action="updated",
        details={
            "before": before,
            "after": _snapshot(leave_year),
        },
    )

    session.refresh(leave_year)
    return leave_year


def removal_impact(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
) -> RemovalImpact:
    """Describe records that belong exclusively to a leave year."""

    from annual_entitlement.persistence import (
        AppliedEntitlementRecord,
        EntitlementRecommendationRecord,
    )
    from job_plans.persistence import JobPlanRecord
    from leave_bookings.persistence import LeaveBookingRecord

    leave_year = get_leave_year(session, consultant_id, leave_year_id)
    job_plan_count = (
        session.scalar(
            select(func.count())
            .select_from(JobPlanRecord)
            .where(JobPlanRecord.leave_year_id == leave_year.id)
        )
        or 0
    )
    recommendation_count = (
        session.scalar(
            select(func.count())
            .select_from(EntitlementRecommendationRecord)
            .where(EntitlementRecommendationRecord.leave_year_id == leave_year.id)
        )
        or 0
    )
    application_count = (
        session.scalar(
            select(func.count())
            .select_from(AppliedEntitlementRecord)
            .where(AppliedEntitlementRecord.leave_year_id == leave_year.id)
        )
        or 0
    )
    booking_count = (
        session.scalar(
            select(func.count())
            .select_from(LeaveBookingRecord)
            .where(LeaveBookingRecord.leave_year_id == leave_year.id)
        )
        or 0
    )

    return RemovalImpact(
        resource_name=f"{leave_year.start_date:%d %b %Y} - {leave_year.end_date:%d %b %Y}",
        action="delete",
        confirmation_text="DELETE",
        consequences=(
            f"{job_plan_count} job plan(s) will be deleted.",
            f"{recommendation_count} calculation snapshot(s) will be deleted.",
            f"{application_count} applied entitlement record(s) will be deleted.",
            f"{booking_count} leave booking(s) are recorded in this year.",
            "The removal will remain recorded in the consultant audit history.",
        ),
        can_proceed=booking_count == 0,
        blocking_reason=(
            "This leave year contains saved leave and must be retained for history."
            if booking_count
            else None
        ),
    )


def remove_leave_year(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    command: RemovalCommand,
) -> RemovalResult:
    """Delete a setup leave year and its owned configuration."""

    if command.confirmation.strip() != "DELETE":
        raise ApiError(
            status_code=422,
            code="confirmation_mismatch",
            message="Enter DELETE to confirm removal.",
        )

    leave_year = get_leave_year(session, consultant_id, leave_year_id)
    impact = removal_impact(session, consultant_id, leave_year_id)
    if not impact.can_proceed:
        raise ApiError(
            status_code=409,
            code="leave_year_has_leave_bookings",
            message=impact.blocking_reason or "This leave year contains saved leave.",
        )
    record_audit_event(
        session,
        consultant_id=consultant_id,
        entity_type="leave_year",
        entity_id=leave_year.id,
        action="deleted",
        details={"before": _snapshot(leave_year), "consequences": impact.consequences},
    )
    session.delete(leave_year)
    session.flush()
    return RemovalResult(message="The leave year was deleted.")
