"""Booking persistence joined to the pure leave calculation engine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from annual_entitlement import AppliedEntitlement
from annual_entitlement import service as entitlement_service
from audit import record_audit_event
from carry_forward import service as carry_forward_service
from domain import CalculationResult, CalculationWarning, DateRange, Hours, LeaveState, RuleId
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

from .persistence import LeaveBookingDayRecord, LeaveBookingRecord
from .schemas import (
    ActivityHoursRead,
    BalanceRead,
    LeaveBookingRead,
    LeaveBookingWrite,
    LeaveDayRead,
    LeavePreviewRead,
    LeaveWarningRead,
    PlanningRead,
)


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
        )
        for day in generated
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
                hours=_hours(carry.hours, Decimal("0"), Decimal("0")),
            ),
        )
        if carry.hours > 0
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
        standard=_hours_read(day.standard_hours),
        deduction=_hours_read(day.deduction_hours),
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
        projected=_balance_read(value.projected) if has_entitlement else None,
        confirmed=_balance_read(value.confirmed) if has_entitlement else None,
        actual=_balance_read(value.actual) if has_entitlement else None,
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

    action = "updated" if record else "created"
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
        days=tuple(_day_read(_domain_day(day, state), holiday_names) for day in record.days),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def create_booking(
    session: Session, consultant_id: int, leave_year_id: int, details: LeaveBookingWrite
) -> PlanningRead:
    _save(session, consultant_id, leave_year_id, details)
    return planning(session, consultant_id, leave_year_id)


def update_booking(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    booking_id: int,
    details: LeaveBookingWrite,
) -> PlanningRead:
    record = _record(session, leave_year_id, booking_id)
    _save(session, consultant_id, leave_year_id, details, record)
    return planning(session, consultant_id, leave_year_id)


def cancel_booking(
    session: Session, consultant_id: int, leave_year_id: int, booking_id: int
) -> PlanningRead:
    leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    record = _record(session, leave_year_id, booking_id)
    before = record.state
    record.state = LeaveState.CANCELLED.value
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
        projected=preview.projected,
        confirmed=preview.confirmed,
        actual=preview.actual,
        warnings=preview.warnings,
    )
