"""Booking persistence joined to the pure leave calculation engine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from annual_entitlement import AppliedEntitlement
from annual_entitlement import service as entitlement_service
from audit import record_audit_event
from carry_forward import service as carry_forward_service
from consultants.models import Consultant
from domain import (
    CalculationResult,
    CalculationWarning,
    DateRange,
    Hours,
    LeaveState,
    ProgrammedActivities,
    RuleId,
)
from errors import ApiError
from job_plans import JobPlanHistory
from job_plans import service as job_plan_service
from leave_records import (
    ZERO_ACTIVITY_HOURS,
    ActivityHours,
    BalanceView,
    CarryForward,
    DailyLeaveOverride,
    LeaveBooking,
    LeaveDay,
    LeaveRecordsRequest,
    LeaveRecordsResult,
    calculate_leave_records_from_days,
    expand_booking,
)
from leave_years import service as leave_year_service
from leave_years.models import LeaveYear
from public_holidays import PublicHolidayRequest, PublicHolidayResult, calculate_public_holidays
from public_holidays import service as holiday_service
from workspaces.events import record_workspace_event
from workspaces.models import WorkspaceEvent
from workspaces.service import current_access

from .persistence import LeaveBookingDayRecord, LeaveBookingRecord
from .schemas import (
    ActivityHoursRead,
    BalanceRead,
    DailyOverrideWrite,
    LeaveBookingRead,
    LeaveBookingWrite,
    LeaveDayRead,
    LeavePreviewRead,
    LeaveRequestActivityRead,
    LeaveRequestQueueItemRead,
    LeaveRequestQueueRead,
    LeaveRequestReviewRead,
    LeaveRequestWrite,
    LeaveWarningRead,
    PlanningRead,
)


@dataclass(frozen=True, slots=True)
class BookingRegenerationImpact:
    """Aggregate effect of rebuilding active booking-day snapshots."""

    affected_bookings: int
    affected_booking_days: int
    current: ActivityHours
    updated: ActivityHours


@dataclass(frozen=True, slots=True)
class _BookingSnapshotChange:
    record: LeaveBookingRecord
    generated_days: tuple[LeaveDay, ...]
    affected_dates: frozenset[date]


def _records(session: Session, leave_year_id: int) -> tuple[LeaveBookingRecord, ...]:
    statement = (
        select(LeaveBookingRecord)
        .options(selectinload(LeaveBookingRecord.days))
        .where(LeaveBookingRecord.leave_year_id == leave_year_id)
        .order_by(LeaveBookingRecord.start_date, LeaveBookingRecord.id)
    )
    return tuple(session.scalars(statement))


def _record(session: Session, leave_year_id: int, booking_id: int) -> LeaveBookingRecord:
    statement = (
        select(LeaveBookingRecord)
        .options(selectinload(LeaveBookingRecord.days))
        .where(
            LeaveBookingRecord.id == booking_id,
            LeaveBookingRecord.leave_year_id == leave_year_id,
        )
    )
    record = session.scalar(statement)
    if record is None:
        raise ApiError(
            status_code=404,
            code="leave_booking_not_found",
            message="The leave booking could not be found.",
        )
    return record


def _hours(dcc: Decimal, spa: Decimal, other: Decimal) -> ActivityHours:
    return ActivityHours(Hours(dcc), Hours(spa), Hours(other))


def _hours_read(value: ActivityHours) -> ActivityHoursRead:
    return ActivityHoursRead(
        dcc_hours=value.dcc.value,
        spa_hours=value.spa.value,
        other_hours=value.other.value,
        total_hours=value.total.value,
    )


def _holiday_result(
    session: Session, leave_year: LeaveYear, history: JobPlanHistory
) -> PublicHolidayResult:
    calendar = holiday_service.active_calendar(session)
    return calculate_public_holidays(
        PublicHolidayRequest(
            leave_year=DateRange(leave_year.start_date, leave_year.end_date),
            employment_start=leave_year.employment_start or leave_year.start_date,
            employment_end=leave_year.employment_end,
            calendar=calendar,
            job_plans=history,
            treatments=holiday_service.treatments_for_leave_year(session, leave_year.id),
        )
    ).value


def _domain_booking(record: LeaveBookingRecord) -> LeaveBooking:
    return LeaveBooking(
        booking_id=str(record.id),
        period=DateRange(record.start_date, record.end_date),
        state=LeaveState(record.state),
        note=record.note,
    )


def _domain_day(record: LeaveBookingDayRecord, state: LeaveState) -> LeaveDay:
    job_plan_version = (
        RuleId(f"job-plan.{record.job_plan_id}")
        if record.job_plan_id is not None
        else RuleId("job-plan.snapshot")
    )
    return LeaveDay(
        booking_id=str(record.booking_id),
        leave_date=record.leave_date,
        state=state,
        job_plan_version=job_plan_version,
        standard_hours=_hours(
            record.standard_dcc_hours,
            record.standard_spa_hours,
            record.standard_other_hours,
        ),
        deduction_hours=_hours(
            record.deduction_dcc_hours,
            record.deduction_spa_hours,
            record.deduction_other_hours,
        ),
        override_reason=record.override_reason,
        contracted_pas=(
            ProgrammedActivities(record.contracted_pas)
            if record.contracted_pas is not None
            else None
        ),
        deduction_factor=(
            Decimal(record.deduction_factor) if record.deduction_factor is not None else None
        ),
    )


def _booking(details: LeaveBookingWrite, booking_id: str) -> LeaveBooking:
    return LeaveBooking(
        booking_id=booking_id,
        period=DateRange(details.start_date, details.end_date),
        state=details.state,
        note=details.note,
        overrides=tuple(
            DailyLeaveOverride(
                leave_date=item.leave_date,
                dcc_hours=Hours(item.dcc_hours) if item.dcc_hours is not None else None,
                spa_hours=Hours(item.spa_hours) if item.spa_hours is not None else None,
                other_hours=Hours(item.other_hours) if item.other_hours is not None else None,
                reason=item.reason,
            )
            for item in details.overrides
        ),
    )


def _validate_period(leave_year: LeaveYear, details: LeaveBookingWrite) -> None:
    active_start = max(
        leave_year.start_date,
        leave_year.employment_start or leave_year.start_date,
    )
    active_end = min(
        leave_year.end_date,
        leave_year.employment_end or leave_year.end_date,
    )
    if details.start_date < active_start or details.end_date > active_end:
        raise ApiError(
            status_code=422,
            code="leave_booking_outside_active_period",
            message="The booking must fall inside the consultant's active leave-year period.",
        )


def _generated_days(
    details: LeaveBookingWrite,
    history: JobPlanHistory,
    holidays: PublicHolidayResult,
    booking_id: str,
) -> tuple[LeaveDay, ...]:
    try:
        generated = expand_booking(_booking(details, booking_id), history)
    except LookupError as error:
        raise ApiError(
            status_code=422,
            code="job_plan_gap",
            message="A job plan must cover every booking date.",
        ) from error

    holiday_names = {item.holiday.holiday_date: item.holiday.name for item in holidays.occurrences}
    return tuple(
        LeaveDay(
            booking_id=day.booking_id,
            leave_date=day.leave_date,
            state=day.state,
            job_plan_version=day.job_plan_version,
            standard_hours=day.standard_hours,
            deduction_hours=(
                ZERO_ACTIVITY_HOURS if day.leave_date in holiday_names else day.deduction_hours
            ),
            override_reason=day.override_reason,
            contracted_pas=day.contracted_pas,
            deduction_factor=day.deduction_factor,
        )
        for day in generated
    )


def _booking_write(
    record: LeaveBookingRecord,
    holiday_dates: set[date],
) -> LeaveBookingWrite:
    overrides = []
    for day in record.days:
        changed = (
            day.deduction_dcc_hours != day.standard_dcc_hours
            or day.deduction_spa_hours != day.standard_spa_hours
            or day.deduction_other_hours != day.standard_other_hours
        )
        if day.leave_date not in holiday_dates and (changed or day.override_reason is not None):
            overrides.append(
                DailyOverrideWrite(
                    leave_date=day.leave_date,
                    dcc_hours=day.deduction_dcc_hours,
                    spa_hours=day.deduction_spa_hours,
                    other_hours=day.deduction_other_hours,
                    reason=day.override_reason,
                )
            )

    return LeaveBookingWrite(
        start_date=record.start_date,
        end_date=record.end_date,
        state=LeaveState(record.state),
        note=record.note,
        overrides=tuple(overrides),
    )


def _same_snapshot(stored: LeaveBookingDayRecord, generated: LeaveDay) -> bool:
    version = str(generated.job_plan_version).rsplit(".", 1)[-1]
    contracted_pas = (
        generated.contracted_pas.value if generated.contracted_pas is not None else None
    )
    factor = generated.deduction_factor
    stored_factor = Decimal(stored.deduction_factor) if stored.deduction_factor else None
    return (
        stored.job_plan_id == int(version)
        and stored.contracted_pas == contracted_pas
        and stored_factor == factor
        and stored.standard_dcc_hours == generated.standard_hours.dcc.value
        and stored.standard_spa_hours == generated.standard_hours.spa.value
        and stored.standard_other_hours == generated.standard_hours.other.value
        and stored.deduction_dcc_hours == generated.deduction_hours.dcc.value
        and stored.deduction_spa_hours == generated.deduction_hours.spa.value
        and stored.deduction_other_hours == generated.deduction_hours.other.value
        and stored.override_reason == generated.override_reason
    )


def _snapshot_changes(
    session: Session,
    leave_year: LeaveYear,
    history: JobPlanHistory,
) -> tuple[_BookingSnapshotChange, ...]:
    holidays = _holiday_result(session, leave_year, history)
    holiday_dates = {item.holiday.holiday_date for item in holidays.occurrences}
    changes = []
    for record in _records(session, leave_year.id):
        if record.state == LeaveState.CANCELLED.value:
            continue
        details = _booking_write(record, holiday_dates)
        generated = _generated_days(details, history, holidays, str(record.id))
        stored_by_date = {day.leave_date: day for day in record.days}
        affected_dates = frozenset(
            day.leave_date
            for day in generated
            if day.leave_date not in stored_by_date
            or not _same_snapshot(stored_by_date[day.leave_date], day)
        )
        affected_dates |= frozenset(set(stored_by_date) - {day.leave_date for day in generated})
        if affected_dates:
            changes.append(
                _BookingSnapshotChange(
                    record=record,
                    generated_days=generated,
                    affected_dates=affected_dates,
                )
            )
    return tuple(changes)


def regeneration_impact(
    session: Session,
    leave_year: LeaveYear,
    history: JobPlanHistory,
) -> BookingRegenerationImpact:
    changes = _snapshot_changes(session, leave_year, history)
    current = ZERO_ACTIVITY_HOURS
    updated = ZERO_ACTIVITY_HOURS
    for change in changes:
        state = LeaveState(change.record.state)
        current_by_date = {day.leave_date: _domain_day(day, state) for day in change.record.days}
        updated_by_date = {day.leave_date: day for day in change.generated_days}
        for leave_date in change.affected_dates:
            if leave_date in current_by_date:
                current += current_by_date[leave_date].calculated_deduction_hours
            if leave_date in updated_by_date:
                updated += updated_by_date[leave_date].calculated_deduction_hours

    return BookingRegenerationImpact(
        affected_bookings=len(changes),
        affected_booking_days=sum(len(change.affected_dates) for change in changes),
        current=current,
        updated=updated,
    )


def _audit_day(day: LeaveDay) -> dict[str, object]:
    return {
        "leave_date": day.leave_date.isoformat(),
        "job_plan_version": str(day.job_plan_version),
        "contracted_pas": (
            format(day.contracted_pas.value, "f") if day.contracted_pas is not None else None
        ),
        "deduction_factor": (
            format(day.deduction_factor, "f") if day.deduction_factor is not None else None
        ),
        "entered_dcc_hours": format(day.deduction_hours.dcc.value, "f"),
        "entered_spa_hours": format(day.deduction_hours.spa.value, "f"),
        "calculated_dcc_hours": format(day.calculated_deduction_hours.dcc.value, "f"),
        "calculated_spa_hours": format(day.calculated_deduction_hours.spa.value, "f"),
    }


def regenerate_booking_days(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    history: JobPlanHistory,
) -> BookingRegenerationImpact:
    leave_year = leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    changes = _snapshot_changes(session, leave_year, history)
    current = ZERO_ACTIVITY_HOURS
    updated = ZERO_ACTIVITY_HOURS
    for change in changes:
        state = LeaveState(change.record.state)
        current_by_date = {day.leave_date: _domain_day(day, state) for day in change.record.days}
        updated_by_date = {day.leave_date: day for day in change.generated_days}
        before = []
        after = []
        for leave_date in sorted(change.affected_dates):
            if leave_date in current_by_date:
                old_day = current_by_date[leave_date]
                current += old_day.calculated_deduction_hours
                before.append(_audit_day(old_day))
            if leave_date in updated_by_date:
                new_day = updated_by_date[leave_date]
                updated += new_day.calculated_deduction_hours
                after.append(_audit_day(new_day))

        _store_days(session, change.record, change.generated_days)
        session.flush()
        record_audit_event(
            session,
            consultant_id=consultant_id,
            entity_type="leave_booking",
            entity_id=change.record.id,
            action="deductions_regenerated",
            details={
                "source": "job_plan_update",
                "before": before,
                "after": after,
            },
        )

    return BookingRegenerationImpact(
        affected_bookings=len(changes),
        affected_booking_days=sum(len(change.affected_dates) for change in changes),
        current=current,
        updated=updated,
    )


def _calculation(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    *,
    candidate: LeaveBooking | None = None,
    candidate_days: tuple[LeaveDay, ...] = (),
    excluding_id: int | None = None,
) -> tuple[
    CalculationResult[LeaveRecordsResult],
    PublicHolidayResult,
    tuple[LeaveBookingRecord, ...],
    bool,
]:
    leave_year = leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    plans = job_plan_service.list_job_plans(session, consultant_id, leave_year_id)
    if not plans:
        raise ApiError(
            status_code=422,
            code="job_plan_required",
            message="Add a job plan before entering leave.",
        )
    history = job_plan_service.calculation_history(plans)
    holidays = _holiday_result(session, leave_year, history)
    records = tuple(
        record for record in _records(session, leave_year_id) if record.id != excluding_id
    )
    bookings = tuple(_domain_booking(record) for record in records)
    days = tuple(
        _domain_day(day, LeaveState(record.state)) for record in records for day in record.days
    )
    if candidate is not None:
        bookings += (candidate,)
        days += candidate_days

    application = entitlement_service.current_application(session, leave_year_id)
    has_entitlement = application is not None
    entitlement = AppliedEntitlement(
        dcc_hours=Hours(application.dcc_hours) if application else Hours(Decimal("0")),
        spa_hours=Hours(application.spa_hours) if application else Hours(Decimal("0")),
        other_hours=Hours(application.other_hours) if application else Hours(Decimal("0")),
    )
    carry = carry_forward_service.get_carry_forward(session, consultant_id, leave_year_id)
    carry_items = (
        (
            CarryForward(
                carry_forward_id=str(carry.id or leave_year_id),
                effective_date=leave_year.start_date,
                hours=_hours(carry.dcc_hours, carry.spa_hours, Decimal("0")),
            ),
        )
        if carry.total_hours > 0
        else ()
    )
    request = LeaveRecordsRequest(
        leave_year=DateRange(leave_year.start_date, leave_year.end_date),
        entitlement=entitlement,
        public_holidays=holidays,
        job_plans=history,
        bookings=bookings,
        carry_forward=carry_items,
    )
    return calculate_leave_records_from_days(request, days), holidays, records, has_entitlement


def _warning_read(warning: CalculationWarning) -> LeaveWarningRead:
    return LeaveWarningRead(
        code=str(warning.rule_id),
        message=warning.message,
        severity=warning.severity.value,
    )


def _balance_read(value: BalanceView) -> BalanceRead:
    return BalanceRead(
        opening=_hours_read(value.opening_entitlement),
        carry_forward=_hours_read(value.carry_forward),
        public_holidays=_hours_read(value.public_holiday_deductions),
        bookings=_hours_read(value.booking_deductions),
        remaining=_hours_read(value.remaining),
    )


def _day_read(day: LeaveDay, holiday_names: dict[date, str]) -> LeaveDayRead:
    version = str(day.job_plan_version)
    job_plan_id = int(version.rsplit(".", 1)[-1]) if version.rsplit(".", 1)[-1].isdigit() else None
    return LeaveDayRead(
        leave_date=day.leave_date,
        job_plan_id=job_plan_id,
        contracted_pas=(day.contracted_pas.value if day.contracted_pas is not None else None),
        deduction_factor=day.deduction_factor,
        standard=_hours_read(day.standard_hours),
        deduction=_hours_read(day.deduction_hours),
        calculated_deduction=_hours_read(day.calculated_deduction_hours),
        override_reason=day.override_reason,
        public_holiday_name=holiday_names.get(day.leave_date),
    )


def _preview_read(
    result: CalculationResult[LeaveRecordsResult],
    holidays: PublicHolidayResult,
    has_entitlement: bool,
) -> LeavePreviewRead:
    holiday_names = {item.holiday.holiday_date: item.holiday.name for item in holidays.occurrences}
    value = result.value
    warnings = tuple(_warning_read(item) for item in result.warnings)
    if not has_entitlement:
        warnings = (
            LeaveWarningRead(
                code="annual-entitlement.required",
                message="Apply annual entitlement to see remaining balances.",
                severity="info",
            ),
            *(item for item in warnings if not item.code.startswith("leave-balance.")),
        )
    return LeavePreviewRead(
        days=tuple(_day_read(day, holiday_names) for day in value.days),
        requested=_balance_read(value.requested) if has_entitlement else None,
        approved=_balance_read(value.approved) if has_entitlement else None,
        warnings=warnings,
    )


def preview_booking(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    details: LeaveBookingWrite,
    excluding_id: int | None = None,
) -> LeavePreviewRead:
    leave_year = leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    _validate_period(leave_year, details)
    plans = job_plan_service.list_job_plans(session, consultant_id, leave_year_id)
    if not plans:
        raise ApiError(
            status_code=422,
            code="job_plan_required",
            message="Add a job plan before entering leave.",
        )
    history = job_plan_service.calculation_history(plans)
    holidays = _holiday_result(session, leave_year, history)
    candidate = _booking(details, f"preview-{excluding_id or 'new'}")
    candidate_days = _generated_days(details, history, holidays, candidate.booking_id)
    result, holidays, _, has_entitlement = _calculation(
        session,
        consultant_id,
        leave_year_id,
        candidate=candidate,
        candidate_days=candidate_days,
        excluding_id=excluding_id,
    )
    preview = _preview_read(result, holidays, has_entitlement)
    candidate_dates = set(candidate.period.dates())
    return preview.model_copy(
        update={"days": tuple(day for day in preview.days if day.leave_date in candidate_dates)}
    )


def _store_days(session: Session, record: LeaveBookingRecord, days: tuple[LeaveDay, ...]) -> None:
    existing = {day.leave_date: day for day in record.days}
    for day in days:
        version = str(day.job_plan_version).rsplit(".", 1)[-1]
        stored = existing.pop(day.leave_date, None)
        if stored is None:
            stored = LeaveBookingDayRecord(leave_date=day.leave_date)
            record.days.append(stored)
        stored.job_plan_id = int(version)
        stored.contracted_pas = day.contracted_pas.value if day.contracted_pas is not None else None
        stored.deduction_factor = (
            format(day.deduction_factor, "f") if day.deduction_factor is not None else None
        )
        stored.standard_dcc_hours = day.standard_hours.dcc.value
        stored.standard_spa_hours = day.standard_hours.spa.value
        stored.standard_other_hours = day.standard_hours.other.value
        stored.deduction_dcc_hours = day.deduction_hours.dcc.value
        stored.deduction_spa_hours = day.deduction_hours.spa.value
        stored.deduction_other_hours = day.deduction_hours.other.value
        stored.override_reason = day.override_reason

    for removed in existing.values():
        session.delete(removed)


def _save(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    details: LeaveBookingWrite,
    record: LeaveBookingRecord | None = None,
    *,
    audit_action: str | None = None,
) -> LeaveBookingRecord:
    leave_year = leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    _validate_period(leave_year, details)
    plans = job_plan_service.list_job_plans(session, consultant_id, leave_year_id)
    if not plans:
        raise ApiError(
            status_code=422,
            code="job_plan_required",
            message="Add a job plan before entering leave.",
        )
    history = job_plan_service.calculation_history(plans)
    holidays = _holiday_result(session, leave_year, history)
    days = _generated_days(details, history, holidays, "save")

    action = audit_action or ("updated" if record else "created")
    before = _snapshot(record) if record else None
    if record is None:
        record = LeaveBookingRecord(leave_year_id=leave_year_id)
        session.add(record)
    record.start_date = details.start_date
    record.end_date = details.end_date
    record.state = details.state.value
    record.note = details.note
    _store_days(session, record, days)
    session.flush()
    record_audit_event(
        session,
        consultant_id=consultant_id,
        entity_type="leave_booking",
        entity_id=record.id,
        action=action,
        details={"before": before, "after": _snapshot(record)},
    )
    return record


def _snapshot(record: LeaveBookingRecord | None) -> dict[str, object] | None:
    if record is None:
        return None
    return {
        "start_date": record.start_date.isoformat(),
        "end_date": record.end_date.isoformat(),
        "state": record.state,
        "note": record.note,
        "cancellation_requested_at": (
            record.cancellation_requested_at.isoformat()
            if record.cancellation_requested_at is not None
            else None
        ),
        "days": len(record.days),
    }


def _record_read(record: LeaveBookingRecord, holiday_names: dict[date, str]) -> LeaveBookingRead:
    state = LeaveState(record.state)
    return LeaveBookingRead(
        id=record.id,
        leave_year_id=record.leave_year_id,
        start_date=record.start_date,
        end_date=record.end_date,
        state=state,
        note=record.note,
        cancellation_requested_at=record.cancellation_requested_at,
        days=tuple(_day_read(_domain_day(day, state), holiday_names) for day in record.days),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def create_booking(
    session: Session, consultant_id: int, leave_year_id: int, details: LeaveBookingWrite
) -> PlanningRead:
    _save(session, consultant_id, leave_year_id, details)
    return planning(session, consultant_id, leave_year_id)


def _request_event_details(
    session: Session,
    consultant_id: int,
    record: LeaveBookingRecord,
) -> dict[str, object]:
    consultant_name = session.scalar(select(Consultant.name).where(Consultant.id == consultant_id))
    return {
        "booking_id": record.id,
        "consultant_id": consultant_id,
        "consultant_name": consultant_name or "Consultant",
        "leave_year_id": record.leave_year_id,
        "start_date": record.start_date.isoformat(),
        "end_date": record.end_date.isoformat(),
    }


def submit_request(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    details: LeaveRequestWrite,
) -> PlanningRead:
    """Create one Member request without accepting client-controlled calculation fields."""

    record = _save(
        session,
        consultant_id,
        leave_year_id,
        LeaveBookingWrite(
            start_date=details.start_date,
            end_date=details.end_date,
            state=LeaveState.REQUESTED,
            note=details.note,
        ),
        audit_action="requested",
    )
    record.requested_by_user_id = current_access(session).user_id or None
    record_workspace_event(
        session,
        event_type="leave_request_submitted",
        details=_request_event_details(session, consultant_id, record),
    )
    session.flush()
    return planning(session, consultant_id, leave_year_id)


def preview_request(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    details: LeaveRequestWrite,
) -> LeavePreviewRead:
    return preview_booking(
        session,
        consultant_id,
        leave_year_id,
        LeaveBookingWrite(
            start_date=details.start_date,
            end_date=details.end_date,
            state=LeaveState.REQUESTED,
            note=details.note,
        ),
    )


def update_booking(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    booking_id: int,
    details: LeaveBookingWrite,
) -> PlanningRead:
    leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    record = _record(session, leave_year_id, booking_id)
    if record.state == LeaveState.REQUESTED.value and details.state != LeaveState.REQUESTED:
        raise ApiError(
            status_code=409,
            code="leave_request_review_required",
            message="Approve or reject this request through the review workflow.",
        )
    if record.cancellation_requested_at is not None:
        raise ApiError(
            status_code=409,
            code="leave_cancellation_review_required",
            message="Review the pending cancellation request before editing this booking.",
        )
    _save(session, consultant_id, leave_year_id, details, record)
    return planning(session, consultant_id, leave_year_id)


def cancel_booking(
    session: Session, consultant_id: int, leave_year_id: int, booking_id: int
) -> PlanningRead:
    leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    record = _record(session, leave_year_id, booking_id)
    before = record.state
    record.state = LeaveState.CANCELLED.value
    record.cancellation_requested_at = None
    record.cancellation_requested_by_user_id = None
    session.flush()
    record_audit_event(
        session,
        consultant_id=consultant_id,
        entity_type="leave_booking",
        entity_id=record.id,
        action="cancelled",
        details={"before": before, "after": record.state},
    )
    return planning(session, consultant_id, leave_year_id)


def cancel_member_request(
    session: Session, consultant_id: int, leave_year_id: int, booking_id: int
) -> PlanningRead:
    leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    record = _record(session, leave_year_id, booking_id)
    if record.state != LeaveState.REQUESTED.value:
        raise ApiError(
            status_code=409,
            code="requested_leave_required",
            message="Only a Requested booking can be cancelled directly.",
        )
    record.state = LeaveState.CANCELLED.value
    session.flush()
    record_audit_event(
        session,
        consultant_id=consultant_id,
        entity_type="leave_booking",
        entity_id=record.id,
        action="request_cancelled",
        details={"before": LeaveState.REQUESTED.value, "after": LeaveState.CANCELLED.value},
    )
    record_workspace_event(
        session,
        event_type="leave_request_cancelled",
        details=_request_event_details(session, consultant_id, record),
    )
    session.flush()
    return planning(session, consultant_id, leave_year_id)


def request_approved_cancellation(
    session: Session, consultant_id: int, leave_year_id: int, booking_id: int
) -> PlanningRead:
    leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    record = _record(session, leave_year_id, booking_id)
    if record.state != LeaveState.APPROVED.value:
        raise ApiError(
            status_code=409,
            code="approved_leave_required",
            message="Only Approved leave can be submitted for cancellation review.",
        )
    if record.cancellation_requested_at is not None:
        raise ApiError(
            status_code=409,
            code="cancellation_already_requested",
            message="Cancellation has already been requested for this booking.",
        )
    access = current_access(session)
    record.cancellation_requested_at = datetime.now(UTC)
    record.cancellation_requested_by_user_id = access.user_id or None
    session.flush()
    record_audit_event(
        session,
        consultant_id=consultant_id,
        entity_type="leave_booking",
        entity_id=record.id,
        action="cancellation_requested",
        details={"state": record.state},
    )
    record_workspace_event(
        session,
        event_type="leave_cancellation_requested",
        details=_request_event_details(session, consultant_id, record),
    )
    session.flush()
    return planning(session, consultant_id, leave_year_id)


def remove_booking(
    session: Session, consultant_id: int, leave_year_id: int, booking_id: int
) -> PlanningRead:
    """Permanently remove an incorrectly entered booking while retaining audit evidence."""

    leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    record = _record(session, leave_year_id, booking_id)
    before = _snapshot(record)
    session.delete(record)
    session.flush()
    record_audit_event(
        session,
        consultant_id=consultant_id,
        entity_type="leave_booking",
        entity_id=booking_id,
        action="deleted",
        details={"before": before},
    )
    return planning(session, consultant_id, leave_year_id)


RequestKind = Literal["leave_request", "cancellation_request"]
RequestEventType = Literal[
    "leave_request_submitted",
    "leave_request_cancelled",
    "leave_cancellation_requested",
]


def _request_kind(record: LeaveBookingRecord) -> RequestKind:
    return (
        "cancellation_request"
        if record.cancellation_requested_at is not None
        else "leave_request"
    )


def request_queue(session: Session) -> LeaveRequestQueueRead:
    """Return actionable requests and durable recent Member request activity."""

    access = current_access(session)
    rows = session.execute(
        select(LeaveBookingRecord, LeaveYear.consultant_id, Consultant.name)
        .join(LeaveYear, LeaveYear.id == LeaveBookingRecord.leave_year_id)
        .join(Consultant, Consultant.id == LeaveYear.consultant_id)
        .where(
            Consultant.workspace_id == access.workspace_id,
            (
                (LeaveBookingRecord.state == LeaveState.REQUESTED.value)
                | (LeaveBookingRecord.cancellation_requested_at.is_not(None))
            ),
        )
        .order_by(LeaveBookingRecord.updated_at.desc(), LeaveBookingRecord.id.desc())
    )
    requests = tuple(
        LeaveRequestQueueItemRead(
            kind=_request_kind(record),
            booking_id=record.id,
            consultant_id=consultant_id,
            consultant_name=consultant_name,
            leave_year_id=record.leave_year_id,
            start_date=record.start_date,
            end_date=record.end_date,
            note=record.note,
            requested_at=record.cancellation_requested_at or record.created_at,
        )
        for record, consultant_id, consultant_name in rows
    )

    event_types = (
        "leave_request_submitted",
        "leave_request_cancelled",
        "leave_cancellation_requested",
    )
    events = tuple(
        session.scalars(
            select(WorkspaceEvent)
            .where(
                WorkspaceEvent.workspace_id == access.workspace_id,
                WorkspaceEvent.event_type.in_(event_types),
            )
            .order_by(WorkspaceEvent.recorded_at.desc(), WorkspaceEvent.id.desc())
            .limit(12)
        )
    )
    activity = []
    for event in events:
        details = json.loads(event.details)
        activity.append(
            LeaveRequestActivityRead(
                id=event.id,
                event_type=cast(RequestEventType, event.event_type),
                actor_label=event.actor_label,
                consultant_name=str(details.get("consultant_name", "Consultant")),
                start_date=date.fromisoformat(str(details["start_date"])),
                end_date=date.fromisoformat(str(details["end_date"])),
                recorded_at=event.recorded_at,
            )
        )
    return LeaveRequestQueueRead(requests=requests, recent_activity=tuple(activity))


def _review_details(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    record: LeaveBookingRecord,
    state: LeaveState,
) -> LeaveBookingWrite:
    leave_year = leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    plans = job_plan_service.list_job_plans(session, consultant_id, leave_year_id)
    history = job_plan_service.calculation_history(plans)
    holidays = _holiday_result(session, leave_year, history)
    holiday_dates = {item.holiday.holiday_date for item in holidays.occurrences}
    return _booking_write(record, holiday_dates).model_copy(update={"state": state})


def review_request(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    booking_id: int,
) -> LeaveRequestReviewRead:
    record = _record(session, leave_year_id, booking_id)
    current = planning(session, consultant_id, leave_year_id)
    kind = _request_kind(record)
    if kind == "leave_request" and record.state != LeaveState.REQUESTED.value:
        raise ApiError(
            status_code=409, code="request_not_pending", message="This request is closed."
        )
    if kind == "cancellation_request" and record.state != LeaveState.APPROVED.value:
        raise ApiError(
            status_code=409, code="request_not_pending", message="This request is closed."
        )

    if kind == "leave_request":
        resulting = preview_booking(
            session,
            consultant_id,
            leave_year_id,
            _review_details(
                session, consultant_id, leave_year_id, record, LeaveState.APPROVED
            ),
            excluding_id=booking_id,
        )
    else:
        result, holidays, _, has_entitlement = _calculation(
            session, consultant_id, leave_year_id, excluding_id=booking_id
        )
        resulting = _preview_read(result, holidays, has_entitlement)

    leave_year = leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    plans = job_plan_service.list_job_plans(session, consultant_id, leave_year_id)
    holiday_result = _holiday_result(
        session, leave_year, job_plan_service.calculation_history(plans)
    )
    holiday_names = {
        item.holiday.holiday_date: item.holiday.name for item in holiday_result.occurrences
    }
    booking = _record_read(record, holiday_names)
    return LeaveRequestReviewRead(
        kind=kind,
        booking=booking,
        current_approved=current.approved,
        resulting_approved=resulting.approved,
        days=resulting.days if kind == "leave_request" else booking.days,
        warnings=resulting.warnings,
    )


def _transition_request(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    booking_id: int,
    *,
    expected_state: LeaveState,
    next_state: LeaveState,
    action: str,
    require_cancellation_request: bool = False,
) -> tuple[PlanningRead, int | None]:
    leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    record = _record(session, leave_year_id, booking_id)
    if record.state != expected_state.value or (
        require_cancellation_request and record.cancellation_requested_at is None
    ):
        raise ApiError(
            status_code=409, code="request_not_pending", message="This request is closed."
        )
    before = _snapshot(record)
    requester_user_id = (
        record.cancellation_requested_by_user_id
        if require_cancellation_request
        else record.requested_by_user_id
    )
    record.state = next_state.value
    record.cancellation_requested_at = None
    record.cancellation_requested_by_user_id = None
    session.flush()
    record_audit_event(
        session,
        consultant_id=consultant_id,
        entity_type="leave_booking",
        entity_id=record.id,
        action=action,
        details={"before": before, "after": _snapshot(record)},
    )
    return planning(session, consultant_id, leave_year_id), requester_user_id


def approve_request(
    session: Session, consultant_id: int, leave_year_id: int, booking_id: int
) -> tuple[PlanningRead, int | None]:
    return _transition_request(
        session,
        consultant_id,
        leave_year_id,
        booking_id,
        expected_state=LeaveState.REQUESTED,
        next_state=LeaveState.APPROVED,
        action="approved",
    )


def reject_request(
    session: Session, consultant_id: int, leave_year_id: int, booking_id: int
) -> tuple[PlanningRead, int | None]:
    return _transition_request(
        session,
        consultant_id,
        leave_year_id,
        booking_id,
        expected_state=LeaveState.REQUESTED,
        next_state=LeaveState.CANCELLED,
        action="rejected",
    )


def approve_cancellation_request(
    session: Session, consultant_id: int, leave_year_id: int, booking_id: int
) -> tuple[PlanningRead, int | None]:
    return _transition_request(
        session,
        consultant_id,
        leave_year_id,
        booking_id,
        expected_state=LeaveState.APPROVED,
        next_state=LeaveState.CANCELLED,
        action="cancellation_approved",
        require_cancellation_request=True,
    )


def reject_cancellation_request(
    session: Session, consultant_id: int, leave_year_id: int, booking_id: int
) -> tuple[PlanningRead, int | None]:
    return _transition_request(
        session,
        consultant_id,
        leave_year_id,
        booking_id,
        expected_state=LeaveState.APPROVED,
        next_state=LeaveState.APPROVED,
        action="cancellation_rejected",
        require_cancellation_request=True,
    )


def planning(session: Session, consultant_id: int, leave_year_id: int) -> PlanningRead:
    leave_year = leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    result, holidays, records, has_entitlement = _calculation(session, consultant_id, leave_year_id)
    preview = _preview_read(result, holidays, has_entitlement)
    holiday_schema = holiday_service.calculate_leave_year_holidays(
        session, consultant_id, leave_year_id
    )
    holiday_names = {item.holiday_date: item.name for item in holiday_schema.occurrences}
    return PlanningRead(
        leave_year_id=leave_year_id,
        start_date=leave_year.start_date,
        end_date=leave_year.end_date,
        holidays=holiday_schema.occurrences,
        bookings=tuple(_record_read(record, holiday_names) for record in records),
        requested=preview.requested,
        approved=preview.approved,
        warnings=preview.warnings,
    )
