"""Expansion of booking ranges into job-plan deductions."""

from __future__ import annotations

from domain import ActivityType
from job_plans import JobPlanHistory

from .models import (
    ActivityHours,
    LeaveBooking,
    LeaveDay,
)


def expand_booking(
    booking: LeaveBooking,
    job_plans: JobPlanHistory,
) -> tuple[LeaveDay, ...]:
    """Generate one calculated record for each booking date."""

    if not isinstance(booking, LeaveBooking):
        raise TypeError("booking must be a LeaveBooking")

    if not isinstance(job_plans, JobPlanHistory):
        raise TypeError("job_plans must be a JobPlanHistory")

    overrides_by_date = {override.leave_date: override for override in booking.overrides}
    generated_days: list[LeaveDay] = []

    for leave_date in booking.period.dates():
        job_plan = job_plans.version_on(leave_date)
        planned_day = job_plan.day_on(leave_date)

        standard = ActivityHours(
            dcc=planned_day.hours_for(ActivityType.DCC),
            spa=planned_day.hours_for(ActivityType.SPA),
            other=planned_day.hours_for(ActivityType.OTHER),
        )

        override = overrides_by_date.get(leave_date)
        if override is None:
            deduction = standard
            override_reason = None
        else:
            deduction = override.apply(standard)
            override_reason = override.reason

        generated_days.append(
            LeaveDay(
                booking_id=booking.booking_id,
                leave_date=leave_date,
                state=booking.state,
                job_plan_version=job_plan.version_id,
                standard_hours=standard,
                deduction_hours=deduction,
                override_reason=override_reason,
            )
        )

    return tuple(generated_days)
