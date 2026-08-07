"""Dated fallback public-holiday snapshots for England and Wales."""

from datetime import date

from .models import (
    HolidayCalendarSource,
    PublicHoliday,
    PublicHolidayCalendar,
)


def _holiday(
    year: int,
    month: int,
    day: int,
    name: str,
    notes: str = "",
) -> PublicHoliday:
    return PublicHoliday(
        holiday_date=date(year, month, day),
        name=name,
        notes=notes,
    )


ENGLAND_WALES_SNAPSHOT = PublicHolidayCalendar(
    source=HolidayCalendarSource.STATIC_SNAPSHOT,
    source_date=date(2026, 8, 6),
    holidays=(
        _holiday(2025, 1, 1, "New Year's Day"),
        _holiday(2025, 4, 18, "Good Friday"),
        _holiday(2025, 4, 21, "Easter Monday"),
        _holiday(2025, 5, 5, "Early May bank holiday"),
        _holiday(2025, 5, 26, "Spring bank holiday"),
        _holiday(2025, 8, 25, "Summer bank holiday"),
        _holiday(2025, 12, 25, "Christmas Day"),
        _holiday(2025, 12, 26, "Boxing Day"),
        _holiday(2026, 1, 1, "New Year's Day"),
        _holiday(2026, 4, 3, "Good Friday"),
        _holiday(2026, 4, 6, "Easter Monday"),
        _holiday(2026, 5, 4, "Early May bank holiday"),
        _holiday(2026, 5, 25, "Spring bank holiday"),
        _holiday(2026, 8, 31, "Summer bank holiday"),
        _holiday(2026, 12, 25, "Christmas Day"),
        _holiday(
            2026,
            12,
            28,
            "Boxing Day",
            "Substitute day",
        ),
        _holiday(2027, 1, 1, "New Year's Day"),
        _holiday(2027, 3, 26, "Good Friday"),
        _holiday(2027, 3, 29, "Easter Monday"),
        _holiday(2027, 5, 3, "Early May bank holiday"),
        _holiday(2027, 5, 31, "Spring bank holiday"),
        _holiday(2027, 8, 30, "Summer bank holiday"),
        _holiday(
            2027,
            12,
            27,
            "Christmas Day",
            "Substitute day",
        ),
        _holiday(
            2027,
            12,
            28,
            "Boxing Day",
            "Substitute day",
        ),
        _holiday(
            2028,
            1,
            3,
            "New Year's Day",
            "Substitute day",
        ),
        _holiday(2028, 4, 14, "Good Friday"),
        _holiday(2028, 4, 17, "Easter Monday"),
        _holiday(2028, 5, 1, "Early May bank holiday"),
        _holiday(2028, 5, 29, "Spring bank holiday"),
        _holiday(2028, 8, 28, "Summer bank holiday"),
        _holiday(2028, 12, 25, "Christmas Day"),
        _holiday(2028, 12, 26, "Boxing Day"),
    ),
)
