"""Job-plan behaviour that maps workbook hours onto leave dates."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from reference_cases.common import cycle, job_plan

from domain import ActivityType, Hours, ProgrammedActivities, RuleId
from job_plans import (
    ActivityAllocation,
    JobPlanCycle,
    JobPlanDay,
    JobPlanHistory,
    JobPlanVersion,
    Weekday,
    leave_deduction_factor,
)


def workbook_cycle() -> JobPlanCycle:
    pattern = {
        (1, Weekday.MONDAY): ((ActivityType.DCC, "8"), (ActivityType.SPA, "0.5")),
        (1, Weekday.TUESDAY): ((ActivityType.DCC, "8"), (ActivityType.SPA, "2")),
        (1, Weekday.WEDNESDAY): ((ActivityType.DCC, "4.5"), (ActivityType.SPA, "1.5")),
    }
    return cycle(
        week_count=1,
        contracted_pas="8.470",
        dcc_pas="5.910",
        spa_pas="2.560",
        pattern=pattern,
    )


def test_workbook_pa_split_and_visible_hours_stay_separate() -> None:
    plan = workbook_cycle()
    assert plan.allocated_pas == ProgrammedActivities.from_value("8.470")
    assert plan.is_reconciled
    assert plan.activity_hours(ActivityType.DCC) == Hours.from_value("20.5")
    assert plan.activity_hours(ActivityType.SPA) == Hours.from_value("4")
    assert plan.actual_cycle_hours == Hours.from_value("24.5")
    assert plan.scheduled_average_weekly_pas.value == Decimal("6.125")


def test_activity_proportions_use_contracted_pas() -> None:
    plan = workbook_cycle()
    assert plan.activity_proportion(ActivityType.DCC) == Decimal("5.910") / Decimal("8.470")
    assert plan.activity_proportion(ActivityType.SPA) == Decimal("2.560") / Decimal("8.470")
    assert plan.activity_proportion(ActivityType.OTHER) == 0


@pytest.mark.parametrize(
    ("contracted_pas", "expected_factor"),
    [
        ("6", "1"),
        ("10", "1"),
        ("12", "0.8333333333333333333333333333"),
    ],
)
def test_leave_deduction_factor_only_caps_plans_above_ten_pa(
    contracted_pas: str,
    expected_factor: str,
) -> None:
    plan = cycle(
        week_count=1,
        contracted_pas=contracted_pas,
        dcc_pas=contracted_pas,
        spa_pas="0",
    )

    assert leave_deduction_factor(plan) == Decimal(expected_factor)


def test_standard_day_returns_exact_activity_hours() -> None:
    monday = workbook_cycle().day(1, Weekday.MONDAY)
    assert monday.total_hours == Hours.from_value("8.5")
    assert monday.hours_for(ActivityType.DCC) == Hours.from_value("8")
    assert monday.hours_for(ActivityType.SPA) == Hours.from_value("0.5")
    assert monday.hours_for(ActivityType.OTHER) == Hours.from_value("0")


def test_two_week_cycle_repeats_from_its_monday_anchor() -> None:
    plan = cycle(
        week_count=2,
        contracted_pas="4",
        dcc_pas="2",
        spa_pas="2",
        pattern={
            (1, Weekday.MONDAY): ((ActivityType.DCC, "8"),),
            (2, Weekday.MONDAY): ((ActivityType.SPA, "8"),),
        },
    )
    anchor = date(2025, 8, 25)
    assert plan.day_on(anchor, cycle_anchor_date=anchor).hours_for(
        ActivityType.DCC
    ) == Hours.from_value("8")
    assert plan.day_on(date(2025, 9, 1), cycle_anchor_date=anchor).hours_for(
        ActivityType.SPA
    ) == Hours.from_value("8")
    assert plan.day_on(date(2025, 9, 8), cycle_anchor_date=anchor).hours_for(
        ActivityType.DCC
    ) == Hours.from_value("8")


def test_pa_mismatch_requires_an_explanation() -> None:
    plan = workbook_cycle()
    with pytest.raises(ValueError, match="do not reconcile"):
        replace(plan, spa_pas=ProgrammedActivities.from_value("2.5"))

    overridden = replace(
        plan,
        spa_pas=ProgrammedActivities.from_value("2.5"),
        reconciliation_override_reason="Approved legacy variance",
    )
    assert overridden.reconciliation_variance == Decimal("-0.060")


def test_cycle_rejects_missing_or_duplicate_positions() -> None:
    plan = workbook_cycle()
    with pytest.raises(ValueError, match="every weekday"):
        replace(plan, days=plan.days[:-1])
    with pytest.raises(ValueError, match="duplicate days"):
        replace(plan, days=(*plan.days[:-1], plan.days[0]))


def test_day_rejects_duplicate_activity_categories() -> None:
    activity = ActivityAllocation(ActivityType.DCC, Hours.from_value("1"))
    with pytest.raises(ValueError, match="repeat"):
        JobPlanDay(1, Weekday.MONDAY, (activity, activity))


def test_history_selects_adjacent_effective_versions() -> None:
    plan = workbook_cycle()
    first = job_plan(
        version_id="job-plan.one",
        effective_from=date(2025, 1, 1),
        effective_to=date(2025, 6, 30),
        job_cycle=plan,
    )
    second = job_plan(
        version_id="job-plan.two",
        effective_from=date(2025, 7, 1),
        effective_to=None,
        job_cycle=plan,
    )
    history = JobPlanHistory((first, second))
    assert history.version_on(date(2025, 6, 30)) is first
    assert history.version_on(date(2025, 7, 1)) is second

    with pytest.raises(ValueError, match="overlap"):
        JobPlanHistory((first, replace(second, effective_from=date(2025, 6, 30))))
    with pytest.raises(LookupError):
        history.version_on(date(2024, 12, 31))


def test_version_requires_valid_dates_and_monday_anchor() -> None:
    version = JobPlanVersion(
        RuleId("job-plan.test"),
        date(2025, 8, 29),
        None,
        date(2025, 8, 25),
        workbook_cycle(),
    )
    assert version.day_on(date(2025, 9, 1)).weekday is Weekday.MONDAY
    with pytest.raises(ValueError, match="Monday"):
        replace(version, cycle_anchor_date=date(2025, 8, 26))
