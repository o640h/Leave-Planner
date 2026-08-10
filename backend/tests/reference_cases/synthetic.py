"""Three synthetic consultant cases required by the roadmap."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from domain import ActivityType, DateRange
from job_plans import JobPlanHistory, Weekday
from leave_records import (
    ActivityHours,
    CarryForward,
    LeaveRecordsRequest,
)
from public_holidays import HolidayTreatmentBasis, PublicHolidayTreatment

from .common import booking, cycle, hours, job_plan, request

CALENDAR_2026 = DateRange(date(2026, 1, 1), date(2026, 12, 31))


def full_time_request() -> LeaveRecordsRequest:
    """A straightforward 10-PA consultant working five DCC days."""

    pattern = {
        (1, weekday): ((ActivityType.DCC, "8"),)
        for weekday in (
            Weekday.MONDAY,
            Weekday.TUESDAY,
            Weekday.WEDNESDAY,
            Weekday.THURSDAY,
            Weekday.FRIDAY,
        )
    }
    full_time_cycle = cycle(
        week_count=1,
        contracted_pas="10",
        dcc_pas="10",
        spa_pas="0",
        pattern=pattern,
    )
    history = JobPlanHistory(
        (
            job_plan(
                version_id="job-plan.synthetic.full-time",
                effective_from=CALENDAR_2026.start,
                effective_to=None,
                job_cycle=full_time_cycle,
            ),
        )
    )
    return request(
        leave_year=CALENDAR_2026,
        employment_start=date(2010, 1, 1),
        consultant_appointment_date=date(2010, 1, 1),
        consultant_service_start_date=date(2010, 1, 1),
        job_plans=history,
        bookings=(
            booking(
                "full-time-week",
                date(2026, 6, 1),
                date(2026, 6, 5),
            ),
        ),
    )


def ltft_uneven_request() -> LeaveRecordsRequest:
    """A 6-PA consultant with long Monday/Tuesday working days."""

    uneven_cycle = cycle(
        week_count=1,
        contracted_pas="6",
        dcc_pas="4.5",
        spa_pas="1.5",
        pattern={
            (1, Weekday.MONDAY): ((ActivityType.DCC, "12"),),
            (1, Weekday.TUESDAY): (
                (ActivityType.DCC, "6"),
                (ActivityType.SPA, "6"),
            ),
        },
    )
    history = JobPlanHistory(
        (
            job_plan(
                version_id="job-plan.synthetic.ltft",
                effective_from=CALENDAR_2026.start,
                effective_to=None,
                job_cycle=uneven_cycle,
            ),
        )
    )
    base_request = request(
        leave_year=CALENDAR_2026,
        employment_start=date(2010, 1, 1),
        consultant_appointment_date=date(2010, 1, 1),
        consultant_service_start_date=date(2010, 1, 1),
        job_plans=history,
        bookings=(
            booking(
                "ltft-two-days",
                date(2026, 6, 1),
                date(2026, 6, 2),
            ),
        ),
        treatments=(
            PublicHolidayTreatment(
                holiday_date=date(2026, 5, 4),
                basis=HolidayTreatmentBasis.QUALIFYING_ON_CALL,
                note="Synthetic case: consultant worked the holiday",
            ),
        ),
    )
    return replace(
        base_request,
        carry_forward=(
            CarryForward(
                carry_forward_id="ltft-carry-forward",
                effective_date=CALENDAR_2026.start,
                hours=ActivityHours(dcc=hours("8")),
            ),
        ),
    )


def capped_multiweek_request() -> LeaveRecordsRequest:
    """A capped 12-PA case with a milestone and in-year plan change."""

    first_cycle = cycle(
        week_count=2,
        contracted_pas="12",
        dcc_pas="9",
        spa_pas="3",
        pattern={
            (1, Weekday.MONDAY): ((ActivityType.DCC, "8"),),
            (1, Weekday.TUESDAY): ((ActivityType.SPA, "4"),),
            (2, Weekday.MONDAY): ((ActivityType.DCC, "10"),),
            (2, Weekday.TUESDAY): ((ActivityType.SPA, "8"),),
        },
    )
    second_cycle = cycle(
        week_count=2,
        contracted_pas="12",
        dcc_pas="8",
        spa_pas="3",
        other_pas="1",
        pattern={
            (1, Weekday.THURSDAY): (
                (ActivityType.DCC, "8"),
                (ActivityType.OTHER, "4"),
            ),
            (1, Weekday.FRIDAY): ((ActivityType.SPA, "4"),),
            (2, Weekday.THURSDAY): ((ActivityType.DCC, "12"),),
            (2, Weekday.FRIDAY): ((ActivityType.SPA, "8"),),
        },
    )
    history = JobPlanHistory(
        (
            job_plan(
                version_id="job-plan.synthetic.capped.1",
                effective_from=CALENDAR_2026.start,
                effective_to=date(2026, 9, 30),
                job_cycle=first_cycle,
            ),
            job_plan(
                version_id="job-plan.synthetic.capped.2",
                effective_from=date(2026, 10, 1),
                effective_to=None,
                job_cycle=second_cycle,
            ),
        )
    )
    return request(
        leave_year=CALENDAR_2026,
        employment_start=date(2019, 7, 1),
        consultant_appointment_date=date(2019, 7, 1),
        consultant_service_start_date=date(2019, 7, 1),
        job_plans=history,
        bookings=(
            booking(
                "capped-change-boundary",
                date(2026, 9, 30),
                date(2026, 10, 2),
            ),
        ),
    )
