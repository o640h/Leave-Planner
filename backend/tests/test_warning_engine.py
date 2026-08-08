"""Readable tests for non-blocking leave warnings."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

from reference_cases import full_time_request
from reference_cases.common import booking

from domain import DateRange, Hours, LeaveState, ProgrammedActivities
from job_plans import JobPlanHistory
from leave_records import (
    ActivityHours,
    AdjustmentKind,
    LeaveAdjustment,
    calculate_leave_records,
)


def _warning_ids(calculated: Any) -> tuple[str, ...]:
    return tuple(str(warning.rule_id) for warning in calculated.warnings)


def test_overlapping_active_bookings_warn_but_cancelled_leave_does_not() -> None:
    """Cancelled history may overlap; active planning records may not silently overlap."""

    request = replace(
        full_time_request(),
        bookings=(
            booking(
                "first",
                date(2026, 6, 1),
                date(2026, 6, 3),
                LeaveState.PLANNED,
            ),
            booking(
                "second",
                date(2026, 6, 3),
                date(2026, 6, 5),
                LeaveState.APPROVED,
            ),
            booking(
                "cancelled",
                date(2026, 6, 1),
                date(2026, 6, 5),
                LeaveState.CANCELLED,
            ),
        ),
    )

    calculated = calculate_leave_records(request)

    assert _warning_ids(calculated) == ("leave-records.overlapping-bookings",)
    assert calculated.warnings[0].affected_period == DateRange(
        date(2026, 6, 3),
        date(2026, 6, 3),
    )
    assert calculated.warnings[0].context["first_booking_id"] == "first"
    assert calculated.warnings[0].context["second_booking_id"] == "second"


def test_negative_total_produces_an_overdrawn_warning_for_each_view() -> None:
    """Adjustments affect all three balance views, so all three are explained."""

    request = replace(
        full_time_request(),
        bookings=(),
        adjustments=(
            LeaveAdjustment(
                adjustment_id="large-sale",
                effective_date=date(2026, 1, 1),
                kind=AdjustmentKind.SOLD_LEAVE,
                hours=ActivityHours(dcc=Hours.from_value("-400")),
                reason="Synthetic overdrawn example",
            ),
        ),
    )

    calculated = calculate_leave_records(request)

    assert _warning_ids(calculated) == (
        "leave-balance.overdrawn.projected",
        "leave-balance.overdrawn.confirmed",
        "leave-balance.overdrawn.actual",
    )


def test_negative_activity_with_positive_total_reports_an_imbalance() -> None:
    """A DCC shortfall must remain visible even if SPA offsets the total."""

    request = replace(
        full_time_request(),
        bookings=(),
        adjustments=(
            LeaveAdjustment(
                adjustment_id="activity-transfer",
                effective_date=date(2026, 1, 1),
                kind=AdjustmentKind.CORRECTION,
                hours=ActivityHours(
                    dcc=Hours.from_value("-400"),
                    spa=Hours.from_value("400"),
                ),
                reason="Synthetic activity imbalance",
            ),
        ),
    )

    calculated = calculate_leave_records(request)

    assert _warning_ids(calculated) == (
        "leave-balance.activity-imbalance.projected",
        "leave-balance.activity-imbalance.confirmed",
        "leave-balance.activity-imbalance.actual",
    )


def test_reconciliation_override_and_carry_forward_are_explained() -> None:
    """Operator overrides remain allowed, but never become invisible."""

    base = full_time_request()
    version = base.job_plans.versions[0]
    mismatched_cycle = replace(
        version.cycle,
        dcc_pas=ProgrammedActivities.from_value("9.5"),
        reconciliation_override_reason="Approved local exception",
    )
    request = replace(
        base,
        job_plans=JobPlanHistory((replace(version, cycle=mismatched_cycle),)),
        adjustments=(
            LeaveAdjustment(
                adjustment_id="carry",
                effective_date=date(2026, 1, 1),
                kind=AdjustmentKind.CARRY_FORWARD,
                hours=ActivityHours(dcc=Hours.from_value("8")),
                reason="Approved carry-forward",
            ),
        ),
    )

    calculated = calculate_leave_records(request)

    assert _warning_ids(calculated) == (
        "job-plan.reconciliation-override",
        "leave-adjustment.carry-forward",
    )
    assert calculated.warnings[0].context["override_reason"] == ("Approved local exception")
    assert calculated.warnings[1].severity.value == "info"
