"""Persisted holiday calendar, correction, and treatment orchestration."""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from audit import record_audit_event
from domain import DateRange
from errors import ApiError
from job_plans import service as job_plan_service
from leave_years import service as leave_year_service
from workspaces.service import current_workspace_id

from .calculator import calculate_public_holidays
from .calendar import resolved_holidays
from .gov_uk import fetch_gov_uk_calendar
from .models import (
    HolidayCalendarSource,
    HolidayCorrectionAction,
    HolidayTreatmentBasis,
    PublicHoliday,
    PublicHolidayCalendar,
    PublicHolidayCorrection,
    PublicHolidayRequest,
    PublicHolidayTreatment,
)
from .persistence import (
    HolidayCalendarEventRecord,
    HolidayCalendarVersionRecord,
    HolidayCorrectionRecord,
    PublicHolidayTreatmentRecord,
)
from .schemas import (
    HolidayCorrectionRead,
    HolidayCorrectionWrite,
    HolidayOccurrenceRead,
    HolidayRead,
    HolidaySettingsRead,
    HolidayTreatmentWrite,
    LeaveYearHolidaysRead,
)
from .snapshots import ENGLAND_WALES_SNAPSHOT


def _store_calendar(session: Session, calendar: PublicHolidayCalendar) -> None:
    record = HolidayCalendarVersionRecord(
        source=calendar.source.value,
        source_date=calendar.source_date,
    )
    record.events.extend(
        HolidayCalendarEventRecord(
            holiday_date=item.holiday_date,
            name=item.name,
            notes=item.notes,
        )
        for item in calendar.holidays
    )
    session.add(record)
    session.flush()


def _latest_calendar_record(session: Session) -> HolidayCalendarVersionRecord:
    statement = (
        select(HolidayCalendarVersionRecord)
        .options(selectinload(HolidayCalendarVersionRecord.events))
        .order_by(HolidayCalendarVersionRecord.id.desc())
    )
    record = session.scalars(statement).first()
    if record is None:
        _store_calendar(session, ENGLAND_WALES_SNAPSHOT)
        record = session.scalars(statement).first()
    assert record is not None
    return record


def _active_corrections(session: Session) -> tuple[HolidayCorrectionRecord, ...]:
    workspace_id = current_workspace_id(session)
    return tuple(
        session.scalars(
            select(HolidayCorrectionRecord)
            .where(
                HolidayCorrectionRecord.workspace_id == workspace_id,
                HolidayCorrectionRecord.retired_at.is_(None),
            )
            .order_by(HolidayCorrectionRecord.holiday_date, HolidayCorrectionRecord.id)
        )
    )


def active_calendar(session: Session) -> PublicHolidayCalendar:
    record = _latest_calendar_record(session)
    return PublicHolidayCalendar(
        source=HolidayCalendarSource(record.source),
        source_date=record.source_date,
        holidays=tuple(
            PublicHoliday(item.holiday_date, item.name, item.notes) for item in record.events
        ),
        corrections=tuple(
            PublicHolidayCorrection(
                holiday_date=item.holiday_date,
                action=HolidayCorrectionAction(item.action),
                replacement_name=item.replacement_name,
                reason=item.reason,
            )
            for item in _active_corrections(session)
        ),
    )


def settings_read(session: Session) -> HolidaySettingsRead:
    calendar = active_calendar(session)
    corrections = _active_corrections(session)
    return HolidaySettingsRead(
        source=calendar.source.value,
        source_date=calendar.source_date,
        holidays=tuple(
            HolidayRead(holiday_date=item.holiday_date, name=item.name, notes=item.notes)
            for item in resolved_holidays(calendar)
        ),
        corrections=tuple(
            HolidayCorrectionRead(
                id=item.id,
                holiday_date=item.holiday_date,
                action=HolidayCorrectionAction(item.action),
                replacement_name=item.replacement_name,
                reason=item.reason,
                created_at=item.created_at,
            )
            for item in corrections
        ),
    )


def _refresh_entitlements(session: Session) -> None:
    """Refresh calculable recommendations; preserve any year needing attention."""

    from annual_entitlement.persistence import AppliedEntitlementRecord
    from annual_entitlement.service import refresh_entitlement
    from consultants.models import Consultant
    from leave_years.models import LeaveYear

    rows = session.execute(
        select(LeaveYear.consultant_id, LeaveYear.id)
        .join(AppliedEntitlementRecord, AppliedEntitlementRecord.leave_year_id == LeaveYear.id)
        .join(Consultant, Consultant.id == LeaveYear.consultant_id)
        .where(Consultant.workspace_id == current_workspace_id(session))
    )
    for consultant_id, leave_year_id in rows:
        try:
            refresh_entitlement(session, consultant_id, leave_year_id)
        except ApiError:
            continue


def sync_calendar(session: Session) -> HolidaySettingsRead:
    try:
        calendar = fetch_gov_uk_calendar(source_date=date.today())
    except (OSError, ValueError) as error:
        raise ApiError(
            status_code=502,
            code="holiday_sync_failed",
            message=(
                "The GOV.UK holiday calendar could not be updated; "
                "the saved calendar remains active."
            ),
        ) from error
    _store_calendar(session, calendar)
    _refresh_entitlements(session)
    return settings_read(session)


def save_correction(session: Session, details: HolidayCorrectionWrite) -> HolidaySettingsRead:
    now = datetime.now(UTC).replace(tzinfo=None)
    for existing in _active_corrections(session):
        if existing.holiday_date == details.holiday_date:
            existing.retired_at = now
    session.add(
        HolidayCorrectionRecord(
            workspace_id=current_workspace_id(session),
            holiday_date=details.holiday_date,
            action=details.action.value,
            replacement_name=details.replacement_name,
            reason=details.reason,
        )
    )
    session.flush()
    _refresh_entitlements(session)
    return settings_read(session)


def remove_correction(session: Session, correction_id: int) -> HolidaySettingsRead:
    record = session.scalar(
        select(HolidayCorrectionRecord).where(
            HolidayCorrectionRecord.id == correction_id,
            HolidayCorrectionRecord.workspace_id == current_workspace_id(session),
        )
    )
    if record is None or record.retired_at is not None:
        raise ApiError(
            status_code=404,
            code="holiday_correction_not_found",
            message="The correction could not be found.",
        )
    record.retired_at = datetime.now(UTC).replace(tzinfo=None)
    session.flush()
    _refresh_entitlements(session)
    return settings_read(session)


def treatments_for_leave_year(
    session: Session, leave_year_id: int
) -> tuple[PublicHolidayTreatment, ...]:
    records = session.scalars(
        select(PublicHolidayTreatmentRecord).where(
            PublicHolidayTreatmentRecord.leave_year_id == leave_year_id
        )
    )
    return tuple(
        PublicHolidayTreatment(
            holiday_date=item.holiday_date,
            basis=HolidayTreatmentBasis(item.basis),
            note=item.note,
        )
        for item in records
    )


def calculate_leave_year_holidays(
    session: Session, consultant_id: int, leave_year_id: int
) -> LeaveYearHolidaysRead:
    leave_year = leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    job_plans = job_plan_service.list_job_plans(session, consultant_id, leave_year_id)
    if not job_plans:
        raise ApiError(
            status_code=422,
            code="job_plan_required",
            message="Add a job plan before reviewing holidays.",
        )
    history = job_plan_service.calculation_history(job_plans)
    calendar = active_calendar(session)
    result = calculate_public_holidays(
        PublicHolidayRequest(
            leave_year=DateRange(leave_year.start_date, leave_year.end_date),
            employment_start=leave_year.employment_start or leave_year.start_date,
            employment_end=leave_year.employment_end,
            calendar=calendar,
            job_plans=history,
            treatments=treatments_for_leave_year(session, leave_year_id),
        )
    ).value
    return LeaveYearHolidaysRead(
        source=calendar.source.value,
        source_date=calendar.source_date,
        entitlement_hours=result.entitlement_hours.value,
        deduction_hours=result.deduction_hours.value,
        occurrences=tuple(
            HolidayOccurrenceRead(
                holiday_date=item.holiday.holiday_date,
                name=item.holiday.name,
                notes=item.holiday.notes,
                basis=item.treatment.basis,
                treatment_note=item.treatment.note,
                contracted_pas=item.contracted_pas.value,
                deduction_factor=item.deduction_factor,
                entitlement_hours=item.entitlement_hours.value,
                dcc_entitlement_hours=item.dcc_entitlement_hours.value,
                spa_entitlement_hours=item.spa_entitlement_hours.value,
                dcc_deduction_hours=item.dcc_deduction_hours.value,
                spa_deduction_hours=item.spa_deduction_hours.value,
            )
            for item in result.occurrences
        ),
    )


def save_treatment(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    holiday_date: date,
    details: HolidayTreatmentWrite,
) -> LeaveYearHolidaysRead:
    leave_year = leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    if not leave_year.start_date <= holiday_date <= leave_year.end_date:
        raise ApiError(
            status_code=422,
            code="holiday_outside_leave_year",
            message="The date is outside this leave year.",
        )
    record = session.scalar(
        select(PublicHolidayTreatmentRecord).where(
            PublicHolidayTreatmentRecord.leave_year_id == leave_year_id,
            PublicHolidayTreatmentRecord.holiday_date == holiday_date,
        )
    )
    if details.basis is HolidayTreatmentBasis.STANDARD:
        if record is not None:
            record_id = record.id
            removed_details = {
                "basis": record.basis,
                "note": record.note,
            }
            session.delete(record)
            session.flush()
            record_audit_event(
                session,
                consultant_id=consultant_id,
                entity_type="public_holiday_treatment",
                entity_id=record_id,
                action="deleted",
                details={
                    "holiday_date": holiday_date.isoformat(),
                    "before": removed_details,
                    "after": None,
                },
            )

        return calculate_leave_year_holidays(session, consultant_id, leave_year_id)

    before = None
    if record is None:
        record = PublicHolidayTreatmentRecord(
            leave_year_id=leave_year_id, holiday_date=holiday_date
        )
        session.add(record)
    else:
        before = {
            "basis": record.basis,
            "note": record.note,
        }
    record.basis = details.basis.value
    record.note = details.note
    session.flush()
    record_audit_event(
        session,
        consultant_id=consultant_id,
        entity_type="public_holiday_treatment",
        entity_id=record.id,
        action="updated" if before else "created",
        details={
            "holiday_date": holiday_date.isoformat(),
            "before": before,
            "after": details.model_dump(mode="json"),
        },
    )
    return calculate_leave_year_holidays(session, consultant_id, leave_year_id)
