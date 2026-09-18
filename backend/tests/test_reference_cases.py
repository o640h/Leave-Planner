"""Golden and synthetic end-to-end calculation cases.

These tests deliberately read like worked examples. They verify the complete
path from policy and job-plan inputs through holidays, records, balances, and
warnings rather than testing one helper in isolation.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from reference_cases import (
    capped_multiweek_request,
    full_time_request,
    ltft_uneven_request,
    workbook_reference_request,
)
from reference_cases.common import booking

from domain import Hours, LeaveState
from leave_records import ActivityHours, calculate_leave_records


def _three_places(hours: Hours) -> Decimal:
    """Compare workbook-facing values while retaining exact values internally."""

    return hours.value.quantize(Decimal("0.001"))


def test_workbook_reference_case_reproduces_all_golden_totals() -> None:
    """The supplied workbook remains the primary regression fixture."""

    calculated = calculate_leave_records(workbook_reference_request())
    approved = calculated.value.approved

    assert _three_places(approved.opening_entitlement.total) == Decimal("291.368")
    assert _three_places(approved.opening_entitlement.dcc) == Decimal("203.304")
    assert _three_places(approved.opening_entitlement.spa) == Decimal("88.064")
    assert approved.carry_forward == ActivityHours(dcc=Hours.from_value("41.25"))
    assert approved.booking_deductions == ActivityHours(
        dcc=Hours.from_value("213.5"),
        spa=Hours.from_value("17"),
    )
    assert approved.public_holiday_deductions == ActivityHours(
        dcc=Hours.from_value("16"),
        spa=Hours.from_value("1"),
    )
    assert _three_places(approved.remaining.dcc) == Decimal("15.054")
    assert _three_places(approved.remaining.spa) == Decimal("70.064")
    assert tuple(str(warning.rule_id) for warning in calculated.warnings) == (
        "leave-balance.carry-forward",
    )


def test_full_time_case_uses_five_days_and_ten_pa_entitlement() -> None:
    calculated = calculate_leave_records(full_time_request())
    approved = calculated.value.approved

    assert approved.opening_entitlement == ActivityHours(dcc=Hours.from_value("352"))
    assert approved.public_holiday_deductions == ActivityHours(dcc=Hours.from_value("64"))
    assert approved.booking_deductions == ActivityHours(dcc=Hours.from_value("40"))
    assert approved.remaining == ActivityHours(dcc=Hours.from_value("248"))
    assert calculated.warnings == ()


def test_ltft_case_keeps_uneven_days_carry_and_worked_holiday() -> None:
    request = ltft_uneven_request()
    calculated = calculate_leave_records(request)
    approved = calculated.value.approved

    # The ledger receives the approved combined opening value rather than the
    # intermediate policy calculation object.
    assert request.entitlement.total_hours == Hours.from_value("211.2")
    assert request.public_holidays.entitlement_hours == Hours.from_value("38.4")
    assert approved.opening_entitlement == ActivityHours(
        dcc=Hours.from_value("158.400"),
        spa=Hours.from_value("52.800"),
    )
    assert approved.public_holiday_deductions == ActivityHours(dcc=Hours.from_value("48"))
    assert approved.booking_deductions == ActivityHours(
        dcc=Hours.from_value("18"),
        spa=Hours.from_value("6"),
    )
    assert approved.remaining == ActivityHours(
        dcc=Hours.from_value("100.400"),
        spa=Hours.from_value("46.800"),
    )
    assert tuple(str(warning.rule_id) for warning in calculated.warnings) == (
        "leave-balance.carry-forward",
    )


def test_capped_case_splits_at_service_milestone_and_job_plan_change() -> None:
    request = capped_multiweek_request()
    calculated = calculate_leave_records(request)
    approved = calculated.value.approved

    # The consultant reaches seven years on 1 July. The applied opening value
    # therefore includes both service tiers plus public-holiday entitlement.
    expected_entitlement = Hours.from_value("272").scale(
        Decimal(181) / Decimal(365)
    ) + Hours.from_value("288").scale(Decimal(184) / Decimal(365))
    assert request.entitlement.total_hours == expected_entitlement + Hours.from_value("64")
    assert request.public_holidays.entitlement_hours == Hours.from_value("64")

    # Twelve PAs affect the activity split, but cannot increase the overall
    # entitlement or holiday value above the ten-PA cap. Dated booking and
    # public-holiday deductions use the workbook's reciprocal cap.
    assert _three_places(approved.opening_entitlement.total) == (
        _three_places(expected_entitlement + Hours.from_value("64"))
    )
    assert _three_places(approved.public_holiday_deductions.dcc) == Decimal("30.000")
    assert _three_places(approved.public_holiday_deductions.spa) == Decimal("3.333")
    assert _three_places(approved.public_holiday_deductions.other) == Decimal("0.000")

    assert _three_places(approved.booking_deductions.dcc) == Decimal("6.667")
    assert _three_places(approved.booking_deductions.spa) == Decimal("3.333")
    assert _three_places(approved.booking_deductions.other) == Decimal("3.333")
    assert tuple(str(day.job_plan_version) for day in calculated.value.days) == (
        "job-plan.synthetic.capped.1",
        "job-plan.synthetic.capped.2",
        "job-plan.synthetic.capped.2",
    )
    assert calculated.warnings == ()


@given(
    requested=st.integers(min_value=0, max_value=4),
    approved=st.integers(min_value=0, max_value=4),
)
def test_lifecycle_deductions_are_always_monotonic(
    requested: int,
    approved: int,
) -> None:
    """Requested usage must never be below approved usage."""

    states = (LeaveState.REQUESTED,) * requested + (LeaveState.APPROVED,) * approved
    first_monday = date(2026, 1, 5)
    bookings = tuple(
        booking(
            f"property-{index}",
            first_monday + timedelta(days=index * 7),
            state=state,
        )
        for index, state in enumerate(states)
    )
    request = replace(full_time_request(), bookings=bookings)
    result = calculate_leave_records(request).value

    assert (
        result.requested.booking_deductions.total.value
        >= result.approved.booking_deductions.total.value
    )
