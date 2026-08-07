"""Public interface for England and Wales public holidays."""

from .calculator import (
    PUBLIC_HOLIDAY_FULL_TIME_HOURS,
    calculate_public_holidays,
)
from .calendar import holidays_in_period, resolved_holidays
from .gov_uk import (
    GOV_UK_BANK_HOLIDAYS_URL,
    fetch_gov_uk_calendar,
    parse_gov_uk_calendar,
)
from .models import (
    HolidayCalendarSource,
    HolidayCorrectionAction,
    HolidayTreatmentBasis,
    PublicHoliday,
    PublicHolidayCalendar,
    PublicHolidayCorrection,
    PublicHolidayOccurrence,
    PublicHolidayRequest,
    PublicHolidayResult,
    PublicHolidayTreatment,
)
from .snapshots import ENGLAND_WALES_SNAPSHOT

__all__ = [
    "ENGLAND_WALES_SNAPSHOT",
    "GOV_UK_BANK_HOLIDAYS_URL",
    "PUBLIC_HOLIDAY_FULL_TIME_HOURS",
    "HolidayCalendarSource",
    "HolidayCorrectionAction",
    "HolidayTreatmentBasis",
    "PublicHoliday",
    "PublicHolidayCalendar",
    "PublicHolidayCorrection",
    "PublicHolidayOccurrence",
    "PublicHolidayRequest",
    "PublicHolidayResult",
    "PublicHolidayTreatment",
    "calculate_public_holidays",
    "fetch_gov_uk_calendar",
    "holidays_in_period",
    "parse_gov_uk_calendar",
    "resolved_holidays",
]
