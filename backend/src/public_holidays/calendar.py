"""Resolution of public-holiday snapshots and manual corrections."""

from __future__ import annotations

from domain import DateRange

from .models import (
    HolidayCorrectionAction,
    PublicHoliday,
    PublicHolidayCalendar,
)


def resolved_holidays(
    calendar: PublicHolidayCalendar,
) -> tuple[PublicHoliday, ...]:
    """Apply manual corrections without changing the source snapshot."""

    holidays_by_date = {holiday.holiday_date: holiday for holiday in calendar.holidays}

    for correction in calendar.corrections:
        if correction.action is HolidayCorrectionAction.REMOVE:
            holidays_by_date.pop(
                correction.holiday_date,
                None,
            )
            continue

        replacement_name = correction.replacement_name
        if replacement_name is None:
            raise ValueError("Add-or-replace correction is missing its name")

        holidays_by_date[correction.holiday_date] = PublicHoliday(
            holiday_date=correction.holiday_date,
            name=replacement_name,
            notes=(f"Trust manual correction: {correction.reason}"),
        )

    return tuple(
        sorted(
            holidays_by_date.values(),
            key=lambda holiday: holiday.holiday_date,
        )
    )


def holidays_in_period(
    calendar: PublicHolidayCalendar,
    period: DateRange,
) -> tuple[PublicHoliday, ...]:
    """Return resolved holidays inside an inclusive date period."""

    return tuple(
        holiday for holiday in resolved_holidays(calendar) if holiday.holiday_date in period
    )
