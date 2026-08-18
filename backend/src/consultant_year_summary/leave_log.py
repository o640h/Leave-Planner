"""Build the consultant-year leave log shared by screen and export."""

from decimal import Decimal

from leave_bookings.schemas import ActivityHoursRead, PlanningRead

from .schemas import LeaveLogEntryRead

ZERO = Decimal("0")


def _activity(dcc: Decimal, spa: Decimal, other: Decimal = ZERO) -> ActivityHoursRead:
    return ActivityHoursRead(
        dcc_hours=dcc,
        spa_hours=spa,
        other_hours=other,
        total_hours=dcc + spa + other,
    )


def leave_log_entries(planning: PlanningRead) -> tuple[LeaveLogEntryRead, ...]:
    """Return chronological booking and public-holiday rows."""

    entries: list[LeaveLogEntryRead] = []
    for booking in planning.bookings:
        amounts = _activity(ZERO, ZERO)
        for day in booking.days:
            deduction = day.calculated_deduction
            amounts = _activity(
                amounts.dcc_hours + deduction.dcc_hours,
                amounts.spa_hours + deduction.spa_hours,
                amounts.other_hours + deduction.other_hours,
            )
        entries.append(
            LeaveLogEntryRead(
                key=f"booking-{booking.id}",
                start_date=booking.start_date,
                end_date=booking.end_date,
                description=booking.note or "Annual Leave",
                state=booking.state.value,
                amounts=amounts,
            )
        )

    entries.extend(
        LeaveLogEntryRead(
            key=f"holiday-{holiday.holiday_date.isoformat()}",
            start_date=holiday.holiday_date,
            end_date=holiday.holiday_date,
            description=holiday.name,
            state="public_holiday",
            amounts=_activity(
                holiday.dcc_deduction_hours,
                holiday.spa_deduction_hours,
            ),
        )
        for holiday in planning.holidays
    )
    return tuple(sorted(entries, key=lambda entry: (entry.start_date, entry.key)))
