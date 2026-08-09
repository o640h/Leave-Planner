"""Partial-year entitlement calculations across effective-date changes."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from reference_cases import capped_multiweek_request, workbook_reference_request

from domain import DateRange, Hours
from entitlement_policy import DEFAULT_ENTITLEMENT_POLICIES
from leave_calculation import (
    LeaveCalculationRequest,
    calculate_leave_entitlement,
    calculate_partial_year_hours,
    completed_service_years,
    service_anniversary,
)


def workbook_request() -> LeaveCalculationRequest:
    request = workbook_reference_request()
    return LeaveCalculationRequest(
        leave_year=request.leave_year,
        employment_start=date(2010, 1, 1),
        employment_end=None,
        consultant_appointment_date=date(2010, 1, 1),
        consultant_service_start_date=date(2010, 1, 1),
        policies=DEFAULT_ENTITLEMENT_POLICIES,
        job_plans=request.job_plans,
    )


def capped_request() -> LeaveCalculationRequest:
    """Recover the pure calculation inputs from the capped ledger fixture."""

    request = capped_multiweek_request()
    return LeaveCalculationRequest(
        leave_year=request.leave_year,
        employment_start=date(2019, 7, 1),
        employment_end=None,
        consultant_appointment_date=date(2019, 7, 1),
        consultant_service_start_date=date(2019, 7, 1),
        policies=DEFAULT_ENTITLEMENT_POLICIES,
        job_plans=request.job_plans,
    )


def test_workbook_periods_match_cached_entitlement() -> None:
    result = calculate_leave_entitlement(workbook_request()).value
    assert tuple(period.period.calendar_days for period in result.periods) == (337, 28)
    assert result.entitlement_hours == Hours.from_value("243.936")
    assert result.dcc_hours == Hours.from_value("170.208")
    assert result.spa_hours.value.quantize(Decimal("0.001")) == Decimal("73.728")


def test_job_plan_change_and_service_milestone_split_periods() -> None:
    entitlement = calculate_leave_entitlement(capped_request()).value
    assert len(entitlement.periods) == 3
    assert entitlement.periods[0].period.end == date(2026, 6, 30)
    assert entitlement.periods[1].completed_service_years == 7
    assert entitlement.periods[-1].job_plan_version.value.endswith("2")
    assert entitlement.entitlement_hours.value.quantize(Decimal("0.001")) == Decimal("280.066")


def test_employment_clips_the_leave_year() -> None:
    request = workbook_request()
    clipped = replace(
        request,
        employment_start=date(2026, 1, 1),
        employment_end=date(2026, 3, 31),
    )
    result = calculate_leave_entitlement(clipped).value
    assert result.active_period == DateRange(date(2026, 1, 1), date(2026, 3, 31))
    assert sum(period.period.calendar_days for period in result.periods) == 90


def test_no_employment_in_year_returns_empty_result() -> None:
    request = replace(workbook_request(), employment_start=date(2030, 1, 1))
    calculated = calculate_leave_entitlement(request)
    assert calculated.value.active_period is None
    assert calculated.value.periods == ()
    assert calculated.trace == ()


def test_trace_explains_every_calculation_period() -> None:
    result = calculate_leave_entitlement(workbook_request())
    rule_ids = {step.rule_id.value for step in result.trace}

    # Each period now explains policy selection and PA proration before showing
    # the calendar-day formula used for that period.
    assert "entitlement.era.from-2005" in rule_ids
    assert "entitlement.tier.from-2005.7-plus" in rule_ids
    assert "entitlement.pa-proration" in rule_ids
    assert "leave-calculation.calendar-days" in rule_ids

    period_steps = [
        step for step in result.trace if step.rule_id.value == "leave-calculation.calendar-days"
    ]
    assert len(period_steps) == len(result.value.periods)
    assert period_steps[0].context["full_year_hours"] == "243.936"


def test_partial_year_uses_the_actual_leave_year_length() -> None:
    assert calculate_partial_year_hours(
        Hours.from_value("366"), included_days=60, leave_year_days=366
    ) == Hours.from_value("60")
    with pytest.raises(ValueError):
        calculate_partial_year_hours(Hours.from_value("1"), included_days=2, leave_year_days=1)


@pytest.mark.parametrize(
    ("start", "years", "expected"),
    [
        (date(2019, 6, 10), 7, date(2026, 6, 10)),
        (date(2020, 2, 29), 1, date(2021, 2, 28)),
        (date(2020, 2, 29), 4, date(2024, 2, 29)),
    ],
)
def test_service_anniversary_handles_leap_days(start: date, years: int, expected: date) -> None:
    assert service_anniversary(start, years) == expected


def test_completed_service_changes_on_anniversary() -> None:
    start = date(2019, 7, 1)
    assert completed_service_years(start, date(2026, 6, 30)) == 6
    assert completed_service_years(start, date(2026, 7, 1)) == 7


def test_structurally_impossible_date_ranges_are_rejected() -> None:
    with pytest.raises(ValueError, match="before"):
        replace(workbook_request(), employment_end=date(2009, 12, 31))
    with pytest.raises(ValueError, match="precede"):
        completed_service_years(date(2026, 1, 1), date(2025, 1, 1))
