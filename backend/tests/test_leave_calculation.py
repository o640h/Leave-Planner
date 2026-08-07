"""Tests for the annual leave calculation.

The tests intentionally use the supplied workbook's numbers and layout where
possible. This keeps the code tied to the small spreadsheet-replacement goal
rather than allowing it to drift into a generic workforce system.
"""

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

import pytest

from domain import DateRange, Hours, ProgrammedActivities, RuleId
from entitlement_policy import DEFAULT_ENTITLEMENT_POLICIES
from job_plans import JobPlanCycle, JobPlanDay, JobPlanHistory, JobPlanVersion, Weekday
from leave_calculation import (
    LeaveCalculationPeriod,
    LeaveCalculationRequest,
    LeaveCalculationResult,
    calculate_leave_entitlement,
    calculate_partial_year_hours,
    completed_service_years,
    service_anniversary,
)


def _cycle(
    *,
    contracted_pas: str = "8.470",
    dcc_pas: str = "5.910",
    spa_pas: str = "2.560",
    other_pas: str = "0",
) -> JobPlanCycle:
    """Create the workbook's PA split with an explicit blank weekday grid.

    Daily hours are deliberately irrelevant here. They will be used later to
    deduct individual leave dates; this calculation uses the contracted PAs.
    """

    return JobPlanCycle(
        week_count=1,
        contracted_pas=ProgrammedActivities.from_value(contracted_pas),
        dcc_pas=ProgrammedActivities.from_value(dcc_pas),
        spa_pas=ProgrammedActivities.from_value(spa_pas),
        other_pas=ProgrammedActivities.from_value(other_pas),
        hours_per_pa=Hours.from_value("4"),
        days=tuple(JobPlanDay(1, weekday) for weekday in Weekday),
    )


def _job_plan(
    *,
    version_id: str,
    effective_from: date,
    effective_to: date | None,
    cycle: JobPlanCycle | None = None,
) -> JobPlanVersion:
    """Create one effective-dated job plan with a valid Monday anchor."""

    anchor = effective_from
    while anchor.weekday() != Weekday.MONDAY:
        anchor = date.fromordinal(anchor.toordinal() - 1)

    return JobPlanVersion(
        version_id=RuleId(version_id),
        effective_from=effective_from,
        effective_to=effective_to,
        cycle_anchor_date=anchor,
        cycle=cycle or _cycle(),
    )


def _workbook_job_plans() -> JobPlanHistory:
    """Mirror the workbook's 337-day and 28-day job-plan periods.

    Excel displays 1 August as both job plan 1's `To` boundary and job plan
    2's `From` boundary. Its subtraction formulas treat the former as
    exclusive. Our domain dates are inclusive, so job plan 1 ends 31 July.
    """

    return JobPlanHistory(
        (
            _job_plan(
                version_id="job-plan.workbook.1",
                effective_from=date(2025, 8, 29),
                effective_to=date(2026, 7, 31),
            ),
            _job_plan(
                version_id="job-plan.workbook.2",
                effective_from=date(2026, 8, 1),
                effective_to=None,
            ),
        )
    )


def _request(
    *,
    leave_year: DateRange | None = None,
    employment_start: date = date(2010, 1, 1),
    employment_end: date | None = None,
    consultant_service_start_date: date = date(2010, 1, 1),
    job_plans: JobPlanHistory | None = None,
) -> LeaveCalculationRequest:
    return LeaveCalculationRequest(
        leave_year=leave_year or DateRange(date(2025, 8, 29), date(2026, 8, 28)),
        employment_start=employment_start,
        employment_end=employment_end,
        consultant_appointment_date=date(2010, 1, 1),
        consultant_service_start_date=consultant_service_start_date,
        policies=DEFAULT_ENTITLEMENT_POLICIES,
        job_plans=job_plans or _workbook_job_plans(),
    )


def test_workbook_calendar_day_split_matches_its_cached_results() -> None:
    """The workbook apportions 291.368 hours over 337 and 28 days."""

    annual_hours = Hours.from_value("291.368")
    first = calculate_partial_year_hours(
        annual_hours,
        included_days=337,
        leave_year_days=365,
    )
    second = calculate_partial_year_hours(
        annual_hours,
        included_days=28,
        leave_year_days=365,
    )

    assert first == Hours.from_value("269.0164821917808219178082192")
    assert second == Hours.from_value("22.35151780821917808219178082")
    assert first + second == annual_hours


def test_workbook_job_plan_boundaries_and_pa_split_are_preserved() -> None:
    """The integrated result should retain both workbook job-plan periods."""

    result = calculate_leave_entitlement(_request()).value

    assert tuple(period.period.calendar_days for period in result.periods) == (337, 28)
    assert result.entitlement_hours == Hours.from_value("243.936")
    assert result.dcc_hours == Hours.from_value("170.208")
    # Decimal division can retain a harmless remainder far below the display
    # precision; the activity totals still reconcile exactly to entitlement.
    assert result.spa_hours.value.quantize(Decimal("0.001")) == Decimal("73.728")
    assert result.other_hours == Hours.from_value("0")
    assert result.dcc_hours + result.spa_hours == result.entitlement_hours


def test_calculation_splits_at_a_service_milestone() -> None:
    """A seventh service anniversary changes the annual rate on that day."""

    leave_year = DateRange(date(2025, 7, 1), date(2026, 6, 30))
    job_plans = JobPlanHistory(
        (
            _job_plan(
                version_id="job-plan.full-year",
                effective_from=leave_year.start,
                effective_to=None,
                cycle=_cycle(contracted_pas="10", dcc_pas="8", spa_pas="2"),
            ),
        )
    )
    request = _request(
        leave_year=leave_year or DateRange(date(2025, 8, 29), date(2026, 8, 28)),
        consultant_service_start_date=date(2019, 1, 1),
        job_plans=job_plans,
    )

    result = calculate_leave_entitlement(request).value

    assert tuple(period.period for period in result.periods) == (
        DateRange(date(2025, 7, 1), date(2025, 12, 31)),
        DateRange(date(2026, 1, 1), date(2026, 6, 30)),
    )
    assert tuple(period.full_year_hours for period in result.periods) == (
        Hours.from_value("272"),
        Hours.from_value("288"),
    )
    expected = Hours.from_value("272").scale(Decimal(184) / Decimal(365)) + Hours.from_value(
        "288"
    ).scale(Decimal(181) / Decimal(365))
    assert result.entitlement_hours == expected


def test_employment_dates_clip_the_calculated_period() -> None:
    """Only days employed inside the leave year should contribute."""

    request = _request(
        employment_start=date(2026, 1, 1),
        employment_end=date(2026, 6, 30),
    )

    result = calculate_leave_entitlement(request).value

    assert result.active_period == DateRange(date(2026, 1, 1), date(2026, 6, 30))
    assert sum(period.period.calendar_days for period in result.periods) == 181
    assert result.entitlement_hours == calculate_partial_year_hours(
        Hours.from_value("243.936"),
        included_days=181,
        leave_year_days=365,
    )


def test_no_employment_in_leave_year_returns_an_empty_result() -> None:
    result = calculate_leave_entitlement(
        _request(
            employment_start=date(2027, 1, 1),
            employment_end=None,
        )
    )

    assert result.value.active_period is None
    assert result.value.periods == ()
    assert result.value.entitlement_hours == Hours.from_value("0")
    assert result.trace == ()


def test_trace_explains_each_effective_period() -> None:
    result = calculate_leave_entitlement(_request())

    assert len(result.trace) == 2
    assert result.trace[0].rule_id == RuleId("leave-calculation.calendar-days")
    assert result.trace[0].context["calendar_days"] == "337"
    assert result.trace[1].context["job_plan_version"] == "job-plan.workbook.2"
    assert result.trace[0].amount == result.value.periods[0].entitlement_hours


def test_leap_year_uses_366_as_its_denominator() -> None:
    """Partial-year calculations must not assume every year has 365 days."""

    leave_year = DateRange(date(2028, 1, 1), date(2028, 12, 31))
    job_plans = JobPlanHistory(
        (
            _job_plan(
                version_id="job-plan.leap-year",
                effective_from=leave_year.start,
                effective_to=None,
                cycle=_cycle(contracted_pas="10", dcc_pas="10", spa_pas="0"),
            ),
        )
    )
    request = _request(
        leave_year=leave_year or DateRange(date(2025, 8, 29), date(2026, 8, 28)),
        employment_start=date(2028, 7, 2),
        job_plans=job_plans,
    )

    result = calculate_leave_entitlement(request).value

    assert leave_year.calendar_days == 366
    assert result.active_period is not None
    assert result.active_period.calendar_days == 183
    assert result.entitlement_hours == Hours.from_value("144")


@pytest.mark.parametrize(
    ("service_start", "completed_years", "expected"),
    [
        (date(2020, 2, 29), 1, date(2021, 2, 28)),
        (date(2020, 2, 29), 4, date(2024, 2, 29)),
        (date(2019, 3, 10), 7, date(2026, 3, 10)),
    ],
)
def test_service_anniversary_handles_ordinary_and_leap_day_starts(
    service_start: date,
    completed_years: int,
    expected: date,
) -> None:
    assert service_anniversary(service_start, completed_years) == expected


def test_completed_service_years_changes_on_the_anniversary() -> None:
    start = date(2019, 8, 10)

    assert completed_service_years(start, date(2026, 8, 9)) == 6
    assert completed_service_years(start, date(2026, 8, 10)) == 7


@pytest.mark.parametrize(
    ("changes", "error_type", "message"),
    [
        ({"leave_year": cast(Any, "bad")}, TypeError, "DateRange"),
        ({"employment_start": cast(Any, datetime(2025, 1, 1))}, TypeError, "date"),
        ({"employment_end": cast(Any, datetime(2026, 1, 1))}, TypeError, "date"),
        ({"employment_end": date(2009, 12, 31)}, ValueError, "before"),
        ({"consultant_appointment_date": cast(Any, "bad")}, TypeError, "date"),
        ({"consultant_service_start_date": cast(Any, "bad")}, TypeError, "date"),
        ({"policies": cast(Any, "bad")}, TypeError, "Catalogue"),
        ({"job_plans": cast(Any, "bad")}, TypeError, "JobPlanHistory"),
    ],
)
def test_request_rejects_structurally_invalid_inputs(
    changes: dict[str, Any],
    error_type: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        replace(_request(), **changes)


@pytest.mark.parametrize(
    ("included_days", "leave_year_days", "error_type", "message"),
    [
        (cast(Any, True), 365, TypeError, "integer"),
        (1, cast(Any, True), TypeError, "integer"),
        (1, 0, ValueError, "greater than zero"),
        (-1, 365, ValueError, "between"),
        (366, 365, ValueError, "between"),
    ],
)
def test_partial_year_calculation_rejects_invalid_day_counts(
    included_days: int,
    leave_year_days: int,
    error_type: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        calculate_partial_year_hours(
            Hours.from_value("288"),
            included_days=included_days,
            leave_year_days=leave_year_days,
        )


def test_public_functions_reject_wrong_types_and_invalid_dates() -> None:
    with pytest.raises(TypeError, match="Hours"):
        calculate_partial_year_hours(
            cast(Any, Decimal("288")), included_days=1, leave_year_days=365
        )
    with pytest.raises(TypeError, match="Service start"):
        service_anniversary(cast(Any, datetime(2020, 1, 1)), 1)
    with pytest.raises(TypeError, match="integer"):
        service_anniversary(date(2020, 1, 1), cast(Any, True))
    with pytest.raises(ValueError, match="negative"):
        service_anniversary(date(2020, 1, 1), -1)
    with pytest.raises(TypeError, match="Service start"):
        completed_service_years(cast(Any, "bad"), date(2020, 1, 1))
    with pytest.raises(TypeError, match="Calculation date"):
        completed_service_years(date(2020, 1, 1), cast(Any, datetime(2021, 1, 1)))
    with pytest.raises(ValueError, match="precede"):
        completed_service_years(date(2020, 1, 2), date(2020, 1, 1))
    with pytest.raises(TypeError, match="LeaveCalculationRequest"):
        calculate_leave_entitlement(cast(Any, "bad"))


def test_result_and_period_models_validate_their_public_fields() -> None:
    valid_period = calculate_leave_entitlement(_request()).value.periods[0]
    valid_result = calculate_leave_entitlement(_request()).value

    with pytest.raises(TypeError, match="Decimal"):
        replace(valid_period, year_fraction=cast(Any, "0.5"))
    with pytest.raises(ValueError, match="finite"):
        replace(valid_period, year_fraction=Decimal("NaN"))
    with pytest.raises(ValueError, match="between"):
        replace(valid_period, year_fraction=Decimal("1.1"))
    with pytest.raises(TypeError, match="Hours"):
        replace(valid_period, entitlement_hours=cast(Any, Decimal("1")))
    with pytest.raises(TypeError, match="tuple"):
        replace(valid_result, periods=cast(Any, []))
    with pytest.raises(TypeError, match="LeaveCalculationPeriod"):
        LeaveCalculationResult(
            valid_result.leave_year, valid_result.active_period, cast(Any, ("bad",))
        )

    assert isinstance(valid_period, LeaveCalculationPeriod)
