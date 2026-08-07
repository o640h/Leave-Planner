"""Workbook-focused tests for leave bookings, deductions, and balances."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any, cast

import pytest

from domain import ActivityType, DateRange, Hours, LeaveState, ProgrammedActivities, RuleId
from entitlement_policy import DEFAULT_ENTITLEMENT_POLICIES
from job_plans import (
    ActivityAllocation,
    JobPlanCycle,
    JobPlanDay,
    JobPlanHistory,
    JobPlanVersion,
    Weekday,
)
from leave_calculation import (
    LeaveCalculationRequest,
    LeaveCalculationResult,
    calculate_leave_entitlement,
)
from leave_records import (
    ZERO_ACTIVITY_HOURS,
    ActivityHours,
    AdjustmentKind,
    DailyLeaveOverride,
    LeaveAdjustment,
    LeaveBooking,
    LeaveRecordsRequest,
    calculate_leave_records,
    expand_booking,
)
from public_holidays import PublicHolidayResult

LEAVE_YEAR = DateRange(date(2025, 8, 29), date(2026, 8, 28))


def _hours(value: str) -> Hours:
    """Keep exact-hour construction short and obvious in fixtures."""

    return Hours.from_value(value)


def _activity(activity_type: ActivityType, hours: str) -> ActivityAllocation:
    return ActivityAllocation(activity_type, _hours(hours))


def _workbook_cycle() -> JobPlanCycle:
    """Mirror the workbook's standard-hours row and overall PA split."""

    days = [JobPlanDay(1, weekday) for weekday in Weekday]
    days[Weekday.MONDAY] = JobPlanDay(
        1,
        Weekday.MONDAY,
        (_activity(ActivityType.DCC, "8"), _activity(ActivityType.SPA, "0.5")),
    )
    days[Weekday.TUESDAY] = JobPlanDay(
        1,
        Weekday.TUESDAY,
        (_activity(ActivityType.DCC, "8"), _activity(ActivityType.SPA, "2")),
    )
    days[Weekday.WEDNESDAY] = JobPlanDay(
        1,
        Weekday.WEDNESDAY,
        (_activity(ActivityType.DCC, "4.5"), _activity(ActivityType.SPA, "1.5")),
    )
    return JobPlanCycle(
        week_count=1,
        contracted_pas=ProgrammedActivities.from_value("8.470"),
        dcc_pas=ProgrammedActivities.from_value("5.910"),
        spa_pas=ProgrammedActivities.from_value("2.560"),
        other_pas=ProgrammedActivities.from_value("0"),
        hours_per_pa=_hours("4"),
        days=tuple(days),
    )


def _workbook_job_plans() -> JobPlanHistory:
    """Use the workbook's two effective periods and shared pattern."""

    cycle = _workbook_cycle()
    return JobPlanHistory(
        (
            JobPlanVersion(
                RuleId("job-plan.workbook.1"),
                LEAVE_YEAR.start,
                date(2026, 7, 31),
                date(2025, 8, 25),
                cycle,
            ),
            JobPlanVersion(
                RuleId("job-plan.workbook.2"),
                date(2026, 8, 1),
                None,
                date(2026, 7, 27),
                cycle,
            ),
        )
    )


def _entitlement(job_plans: JobPlanHistory) -> LeaveCalculationResult:
    """Use the real annual calculation rather than a fake result."""

    return calculate_leave_entitlement(
        LeaveCalculationRequest(
            leave_year=LEAVE_YEAR,
            employment_start=date(2010, 1, 1),
            employment_end=None,
            consultant_appointment_date=date(2010, 1, 1),
            consultant_service_start_date=date(2010, 1, 1),
            policies=DEFAULT_ENTITLEMENT_POLICIES,
            job_plans=job_plans,
        )
    ).value


def _request(
    *,
    bookings: tuple[LeaveBooking, ...] = (),
    adjustments: tuple[LeaveAdjustment, ...] = (),
) -> LeaveRecordsRequest:
    job_plans = _workbook_job_plans()
    return LeaveRecordsRequest(
        LEAVE_YEAR,
        _entitlement(job_plans),
        PublicHolidayResult(()),
        job_plans,
        bookings,
        adjustments,
    )


def _booking(
    booking_id: str,
    leave_date: date,
    state: LeaveState,
    *,
    dcc: str | None = None,
    spa: str | None = None,
) -> LeaveBooking:
    """Create one day's leave, optionally with workbook-entered hours."""

    overrides: tuple[DailyLeaveOverride, ...] = ()
    if dcc is not None or spa is not None:
        overrides = (
            DailyLeaveOverride(
                leave_date,
                "Workbook reference value",
                dcc_hours=_hours(dcc) if dcc is not None else None,
                spa_hours=_hours(spa) if spa is not None else None,
            ),
        )
    return LeaveBooking(
        booking_id,
        DateRange(leave_date, leave_date),
        state,
        overrides,
    )


def test_range_expands_to_daily_job_plan_deductions() -> None:
    """A range produces one row per date, including zero-hour days."""

    booking = LeaveBooking(
        "range-1",
        DateRange(date(2026, 1, 5), date(2026, 1, 11)),
        LeaveState.PLANNED,
    )
    days = expand_booking(booking, _workbook_job_plans())

    assert len(days) == 7
    assert tuple(day.leave_date for day in days) == tuple(booking.period.dates())
    assert days[0].deduction_hours == ActivityHours(_hours("8"), _hours("0.5"))
    assert days[1].deduction_hours == ActivityHours(_hours("8"), _hours("2"))
    assert days[2].deduction_hours == ActivityHours(_hours("4.5"), _hours("1.5"))
    assert all(day.deduction_hours == ZERO_ACTIVITY_HOURS for day in days[3:])


def test_partial_day_override_replaces_only_the_supplied_category() -> None:
    """Changing Tuesday DCC leaves its normal two SPA hours untouched."""

    leave_date = date(2026, 1, 6)
    booking = LeaveBooking(
        "partial-1",
        DateRange(leave_date, leave_date),
        LeaveState.APPROVED,
        (
            DailyLeaveOverride(
                leave_date,
                "Worked half of the DCC session",
                dcc_hours=_hours("4"),
            ),
        ),
    )
    day = expand_booking(booking, _workbook_job_plans())[0]

    assert day.standard_hours == ActivityHours(_hours("8"), _hours("2"))
    assert day.deduction_hours == ActivityHours(_hours("4"), _hours("2"))
    assert day.override_reason == "Worked half of the DCC session"


def test_lifecycle_states_feed_the_three_balance_views() -> None:
    """Projected is broadest; actual contains only leave already taken."""

    bookings = (
        _booking("planned", date(2026, 1, 5), LeaveState.PLANNED),
        _booking("approved", date(2026, 1, 12), LeaveState.APPROVED),
        _booking("taken", date(2026, 1, 19), LeaveState.TAKEN),
        _booking("cancelled", date(2026, 1, 26), LeaveState.CANCELLED),
    )
    result = calculate_leave_records(_request(bookings=bookings)).value

    assert result.projected.booking_deductions == ActivityHours(_hours("24"), _hours("1.5"))
    assert result.confirmed.booking_deductions == ActivityHours(_hours("16"), _hours("1"))
    assert result.actual.booking_deductions == ActivityHours(_hours("8"), _hours("0.5"))
    assert len(result.days) == 4  # Cancelled remains in history but is not deducted.


def test_adjustments_change_every_balance_and_allow_category_corrections() -> None:
    """Carry, sale, and DCC-to-SPA correction remain explicit records."""

    adjustments = (
        LeaveAdjustment(
            "carry",
            LEAVE_YEAR.start,
            AdjustmentKind.CARRY_FORWARD,
            ActivityHours(dcc=_hours("10")),
            "Approved carry-forward",
        ),
        LeaveAdjustment(
            "sold",
            date(2025, 9, 1),
            AdjustmentKind.SOLD_LEAVE,
            ActivityHours(dcc=_hours("-2")),
            "Two hours sold",
        ),
        LeaveAdjustment(
            "reallocate",
            date(2025, 9, 2),
            AdjustmentKind.CORRECTION,
            ActivityHours(dcc=_hours("-1"), spa=_hours("1")),
            "Correct one hour from DCC to SPA",
        ),
    )
    result = calculate_leave_records(_request(adjustments=adjustments)).value
    expected = ActivityHours(dcc=_hours("7"), spa=_hours("1"))

    assert result.projected.adjustments == expected
    assert result.confirmed.adjustments == expected
    assert result.actual.adjustments == expected


def test_trace_explains_days_adjustments_and_each_balance() -> None:
    booking = _booking("trace-booking", date(2026, 1, 5), LeaveState.TAKEN, dcc="6", spa="0")
    adjustment = LeaveAdjustment(
        "trace-adjustment",
        LEAVE_YEAR.start,
        AdjustmentKind.CARRY_FORWARD,
        ActivityHours(dcc=_hours("2")),
        "Trace example",
    )
    calculated = calculate_leave_records(_request(bookings=(booking,), adjustments=(adjustment,)))

    assert tuple(str(step.rule_id) for step in calculated.trace) == (
        "leave-records.daily-deduction",
        "leave-adjustment.carry_forward",
        "leave-balance.projected",
        "leave-balance.confirmed",
        "leave-balance.actual",
    )
    assert calculated.trace[0].context["overridden"] == "true"
    assert calculated.trace[1].context["reason"] == "Trace example"


def test_booking_rejects_duplicate_or_out_of_range_overrides() -> None:
    leave_date = date(2026, 1, 5)
    override = DailyLeaveOverride(leave_date, "Reason", dcc_hours=_hours("1"))

    with pytest.raises(ValueError, match="multiple overrides"):
        LeaveBooking(
            "duplicate",
            DateRange(leave_date, leave_date),
            LeaveState.PLANNED,
            (override, override),
        )
    with pytest.raises(ValueError, match="inside the booking"):
        LeaveBooking(
            "outside",
            DateRange(date(2026, 1, 6), date(2026, 1, 6)),
            LeaveState.PLANNED,
            (override,),
        )


def test_request_rejects_duplicate_ids_and_records_outside_leave_year() -> None:
    booking = _booking("same", date(2026, 1, 5), LeaveState.PLANNED)
    adjustment = LeaveAdjustment(
        "same",
        LEAVE_YEAR.start,
        AdjustmentKind.CARRY_FORWARD,
        ActivityHours(dcc=_hours("1")),
        "Reason",
    )

    with pytest.raises(ValueError, match="Booking IDs"):
        replace(_request(), bookings=(booking, booking))
    with pytest.raises(ValueError, match="Adjustment IDs"):
        replace(_request(), adjustments=(adjustment, adjustment))
    with pytest.raises(ValueError, match="inside the leave year"):
        replace(
            _request(),
            bookings=(_booking("outside", date(2026, 8, 31), LeaveState.PLANNED),),
        )


def test_public_functions_reject_wrong_input_types() -> None:
    with pytest.raises(TypeError, match="LeaveBooking"):
        expand_booking(cast(Any, "bad"), _workbook_job_plans())
    with pytest.raises(TypeError, match="JobPlanHistory"):
        expand_booking(
            _booking("valid", date(2026, 1, 5), LeaveState.PLANNED),
            cast(Any, "bad"),
        )
    with pytest.raises(TypeError, match="LeaveRecordsRequest"):
        calculate_leave_records(cast(Any, "bad"))
