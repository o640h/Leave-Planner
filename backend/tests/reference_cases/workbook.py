"""Executable version of the supplied workbook's worked example."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from domain import ActivityType, DateRange, LeaveState
from job_plans import JobPlanHistory, Weekday
from leave_records import (
    ActivityHours,
    CarryForward,
    DailyLeaveOverride,
    LeaveBooking,
    LeaveRecordsRequest,
)
from public_holidays import HolidayTreatmentBasis, PublicHolidayTreatment

from .common import cycle, hours, job_plan, request

WORKBOOK_LEAVE_YEAR = DateRange(date(2025, 8, 29), date(2026, 8, 28))

# The two malformed decade dates in Excel are represented by their intended
# dates here. Their entered DCC/SPA values are preserved exactly.
_WORKBOOK_LEAVE_ROWS = (
    (date(2025, 10, 20), "8", "0.5"),
    (date(2025, 10, 21), "8", "2"),
    (date(2025, 10, 22), "4.5", "1.5"),
    (date(2025, 10, 27), "6.5", "0"),
    (date(2025, 12, 8), "8", "0"),
    (date(2025, 12, 9), "8", "2"),
    (date(2025, 12, 10), "4.5", "1.5"),
    (date(2025, 12, 15), "8", "0.5"),
    (date(2025, 12, 16), "8", "2"),
    (date(2025, 12, 17), "4.5", "1.5"),
    (date(2025, 12, 30), "8", "0"),
    (date(2025, 12, 31), "4", "0"),
    (date(2026, 3, 30), "7.5", "0"),
    (date(2026, 3, 31), "4", "0"),
    (date(2026, 4, 1), "4.5", "0"),
    (date(2026, 4, 7), "5", "0"),
    (date(2026, 4, 8), "4.5", "0"),
    (date(2026, 6, 29), "6", "0"),
    (date(2026, 6, 30), "4", "0"),
    (date(2026, 7, 1), "3.5", "0"),
    (date(2026, 7, 6), "6", "0"),
    (date(2026, 7, 7), "4", "0"),
    (date(2026, 7, 8), "4.5", "0"),
    (date(2026, 7, 13), "6", "0"),
    (date(2026, 7, 14), "8", "0"),
    (date(2026, 7, 15), "4.5", "0"),
    (date(2026, 8, 10), "8", "0.5"),
    (date(2026, 8, 11), "8", "2"),
    (date(2026, 8, 12), "4.5", "0"),
    (date(2026, 8, 17), "8", "0.5"),
    (date(2026, 8, 18), "8", "2"),
    (date(2026, 8, 19), "4.5", "0"),
    (date(2026, 8, 24), "8", "0.5"),
    (date(2026, 8, 25), "8", "0"),
    (date(2026, 8, 26), "4.5", "0"),
)


def _workbook_job_plans() -> JobPlanHistory:
    visible_pattern = {
        (1, Weekday.MONDAY): (
            (ActivityType.DCC, "8"),
            (ActivityType.SPA, "0.5"),
        ),
        (1, Weekday.TUESDAY): (
            (ActivityType.DCC, "8"),
            (ActivityType.SPA, "2"),
        ),
        (1, Weekday.WEDNESDAY): (
            (ActivityType.DCC, "4.5"),
            (ActivityType.SPA, "1.5"),
        ),
    }
    workbook_cycle = cycle(
        week_count=1,
        contracted_pas="8.470",
        dcc_pas="5.910",
        spa_pas="2.560",
        pattern=visible_pattern,
    )
    return JobPlanHistory(
        (
            job_plan(
                version_id="job-plan.workbook.1",
                effective_from=WORKBOOK_LEAVE_YEAR.start,
                effective_to=date(2026, 7, 31),
                job_cycle=workbook_cycle,
            ),
            job_plan(
                version_id="job-plan.workbook.2",
                effective_from=date(2026, 8, 1),
                effective_to=None,
                job_cycle=workbook_cycle,
            ),
        )
    )


def _workbook_bookings() -> tuple[LeaveBooking, ...]:
    return tuple(
        LeaveBooking(
            booking_id=f"workbook-{index}",
            period=DateRange(leave_date, leave_date),
            state=LeaveState.TAKEN,
            overrides=(
                DailyLeaveOverride(
                    leave_date=leave_date,
                    reason="Workbook reference value",
                    dcc_hours=hours(dcc),
                    spa_hours=hours(spa),
                ),
            ),
        )
        for index, (leave_date, dcc, spa) in enumerate(
            _WORKBOOK_LEAVE_ROWS,
            start=1,
        )
    )


def workbook_reference_request() -> LeaveRecordsRequest:
    """Build the golden case from workbook inputs, not cached totals."""

    job_plans = _workbook_job_plans()
    base_request = request(
        leave_year=WORKBOOK_LEAVE_YEAR,
        employment_start=date(2010, 1, 1),
        consultant_appointment_date=date(2010, 1, 1),
        consultant_service_start_date=date(2010, 1, 1),
        job_plans=job_plans,
        bookings=_workbook_bookings(),
        treatments=(
            PublicHolidayTreatment(
                holiday_date=date(2026, 5, 4),
                basis=HolidayTreatmentBasis.QUALIFYING_ON_CALL,
                note="Workbook marks this holiday as on-call",
            ),
        ),
    )
    carry_forward = CarryForward(
        carry_forward_id="workbook-carry-forward",
        effective_date=WORKBOOK_LEAVE_YEAR.start,
        hours=ActivityHours(dcc=hours("41.25")),
    )
    return replace(
        base_request,
        carry_forward=(carry_forward,),
    )
