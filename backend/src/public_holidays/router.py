"""Public-holiday settings and consultant-year routes."""

from datetime import date

from fastapi import APIRouter

from dependencies import DatabaseSession

from . import service
from .schemas import (
    HolidayCorrectionWrite,
    HolidaySettingsRead,
    HolidayTreatmentWrite,
    LeaveYearHolidaysRead,
)

settings_router = APIRouter(prefix="/api/settings/public-holidays", tags=["public holidays"])
year_router = APIRouter(
    prefix="/api/consultants/{consultant_id}/leave-years/{leave_year_id}/public-holidays",
    tags=["public holidays"],
)


@settings_router.get("", response_model=HolidaySettingsRead)
def get_settings(session: DatabaseSession) -> HolidaySettingsRead:
    return service.settings_read(session)


@settings_router.post("/sync", response_model=HolidaySettingsRead)
def sync_settings(session: DatabaseSession) -> HolidaySettingsRead:
    return service.sync_calendar(session)


@settings_router.post("/corrections", response_model=HolidaySettingsRead)
def add_correction(
    details: HolidayCorrectionWrite, session: DatabaseSession
) -> HolidaySettingsRead:
    return service.save_correction(session, details)


@settings_router.delete("/corrections/{correction_id}", response_model=HolidaySettingsRead)
def delete_correction(correction_id: int, session: DatabaseSession) -> HolidaySettingsRead:
    return service.remove_correction(session, correction_id)


@year_router.get("", response_model=LeaveYearHolidaysRead)
def get_year_holidays(
    consultant_id: int, leave_year_id: int, session: DatabaseSession
) -> LeaveYearHolidaysRead:
    return service.calculate_leave_year_holidays(session, consultant_id, leave_year_id)


@year_router.put("/{holiday_date}/treatment", response_model=LeaveYearHolidaysRead)
def put_treatment(
    consultant_id: int,
    leave_year_id: int,
    holiday_date: date,
    details: HolidayTreatmentWrite,
    session: DatabaseSession,
) -> LeaveYearHolidaysRead:
    return service.save_treatment(session, consultant_id, leave_year_id, holiday_date, details)
