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
    CarryForward,
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
                LeaveState.REQUESTED,
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
        carry_forward=(
            CarryForward(
                carry_forward_id="carry",
                effective_date=date(2026, 1, 1),
                hours=ActivityHours(dcc=Hours.from_value("8")),
            ),
        ),
    )

    calculated = calculate_leave_records(request)

    assert _warning_ids(calculated) == (
        "job-plan.reconciliation-override",
        "leave-balance.carry-forward",
    )
    assert calculated.warnings[0].context["override_reason"] == ("Approved local exception")
    assert calculated.warnings[1].severity.value == "info"
