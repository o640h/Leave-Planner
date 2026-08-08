"""Leave bookings, daily deductions, adjustments, and lifecycle balances."""

from dataclasses import replace
from datetime import date

import pytest
from reference_cases import full_time_request, workbook_reference_request

from domain import DateRange, Hours, LeaveState
from leave_records import (
    ActivityHours,
    AdjustmentKind,
    DailyLeaveOverride,
    LeaveAdjustment,
    LeaveBooking,
    calculate_leave_records,
    expand_booking,
)


def hours(value: str) -> Hours:
    return Hours.from_value(value)


def test_range_expands_to_daily_job_plan_deductions() -> None:
    request = full_time_request()
    booking = request.bookings[0]
    days = expand_booking(booking, request.job_plans)
    assert len(days) == 5
    assert all(day.deduction_hours == ActivityHours(dcc=hours("8")) for day in days)


def test_partial_day_override_replaces_only_supplied_activity() -> None:
    request = workbook_reference_request()
    leave_date = date(2025, 10, 20)
    booking = LeaveBooking(
        "partial",
        DateRange(leave_date, leave_date),
        LeaveState.PLANNED,
        (DailyLeaveOverride(leave_date, "Half day", dcc_hours=hours("4")),),
    )
    day = expand_booking(booking, request.job_plans)[0]
    assert day.standard_hours == ActivityHours(dcc=hours("8"), spa=hours("0.5"))
    assert day.deduction_hours == ActivityHours(dcc=hours("4"), spa=hours("0.5"))
    assert day.is_overridden


@pytest.mark.parametrize(
    ("state", "projected", "confirmed", "actual"),
    [
        (LeaveState.PLANNED, "40", "0", "0"),
        (LeaveState.APPROVED, "40", "40", "0"),
        (LeaveState.TAKEN, "40", "40", "40"),
        (LeaveState.CANCELLED, "0", "0", "0"),
    ],
)
def test_leave_states_feed_the_expected_balance_views(
    state: LeaveState, projected: str, confirmed: str, actual: str
) -> None:
    request = full_time_request()
    booking = replace(request.bookings[0], state=state)
    result = calculate_leave_records(replace(request, bookings=(booking,))).value
    assert result.projected.booking_deductions.dcc == hours(projected)
    assert result.confirmed.booking_deductions.dcc == hours(confirmed)
    assert result.actual.booking_deductions.dcc == hours(actual)


def test_adjustments_change_all_balance_views() -> None:
    request = full_time_request()
    adjustments = (
        LeaveAdjustment(
            "carry",
            request.leave_year.start,
            AdjustmentKind.CARRY_FORWARD,
            ActivityHours(dcc=hours("8")),
            "Approved carry-forward",
        ),
        LeaveAdjustment(
            "sold",
            date(2026, 2, 1),
            AdjustmentKind.SOLD_LEAVE,
            ActivityHours(dcc=hours("-4")),
            "Leave sold",
        ),
        LeaveAdjustment(
            "correction",
            date(2026, 3, 1),
            AdjustmentKind.CORRECTION,
            ActivityHours(spa=hours("2")),
            "SPA correction",
        ),
    )
    result = calculate_leave_records(replace(request, adjustments=adjustments)).value
    expected = ActivityHours(dcc=hours("4"), spa=hours("2"))
    assert result.projected.adjustments == expected
    assert result.confirmed.adjustments == expected
    assert result.actual.adjustments == expected


def test_trace_explains_bookings_adjustments_and_balances() -> None:
    result = calculate_leave_records(workbook_reference_request())
    rule_ids = {step.rule_id.value for step in result.trace}
    assert {
        "leave-records.daily-deduction",
        "leave-adjustment.carry_forward",
        "leave-balance.projected",
        "leave-balance.confirmed",
        "leave-balance.actual",
    } <= rule_ids


def test_booking_overrides_require_reasons_and_valid_dates() -> None:
    leave_date = date(2026, 6, 1)
    with pytest.raises(ValueError, match="reason"):
        DailyLeaveOverride(leave_date, "", dcc_hours=hours("4"))
    with pytest.raises(ValueError, match="at least one"):
        DailyLeaveOverride(leave_date, "No values")

    override = DailyLeaveOverride(leave_date, "Partial", dcc_hours=hours("4"))
    with pytest.raises(ValueError, match="multiple overrides"):
        LeaveBooking(
            "duplicate", DateRange(leave_date, leave_date), LeaveState.PLANNED, (override, override)
        )
    with pytest.raises(ValueError, match="inside"):
        LeaveBooking(
            "outside",
            DateRange(date(2026, 6, 2), date(2026, 6, 2)),
            LeaveState.PLANNED,
            (override,),
        )


def test_request_rejects_duplicate_ids_and_out_of_year_records() -> None:
    request = full_time_request()
    booking = request.bookings[0]
    with pytest.raises(ValueError, match="unique"):
        replace(request, bookings=(booking, booking))

    adjustment = LeaveAdjustment(
        "outside",
        date(2027, 1, 1),
        AdjustmentKind.CORRECTION,
        ActivityHours(dcc=hours("1")),
        "Outside year",
    )
    with pytest.raises(ValueError, match="leave year"):
        replace(request, adjustments=(adjustment,))


def test_adjustment_sign_rules_match_the_operator_action() -> None:
    with pytest.raises(ValueError, match="negative"):
        LeaveAdjustment(
            "carry",
            date(2026, 1, 1),
            AdjustmentKind.CARRY_FORWARD,
            ActivityHours(dcc=hours("-1")),
            "Invalid carry-forward",
        )
    with pytest.raises(ValueError, match="negative"):
        LeaveAdjustment(
            "sold",
            date(2026, 1, 1),
            AdjustmentKind.SOLD_LEAVE,
            ActivityHours(dcc=hours("1")),
            "Invalid sale",
        )
