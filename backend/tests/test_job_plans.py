"""Tests for the small job-plan model used by leave calculations.

The reference fixture mirrors the workbook's two separate inputs:

* overall DCC/SPA PAs allocate annual entitlement; and
* visible weekday hours determine the standard deduction for a leave date.

The workbook's unexplained +3 DCC / +4 SPA formula additions are deliberately
not treated as standard weekday activity.
"""

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

import pytest

from domain import ActivityType, Hours, ProgrammedActivities, RuleId
from job_plans import (
    ActivityAllocation,
    JobPlanCycle,
    JobPlanDay,
    JobPlanHistory,
    JobPlanVersion,
    Weekday,
)


def _activity(activity_type: ActivityType, hours: str) -> ActivityAllocation:
    """Build one exact activity entry without using binary floats."""

    return ActivityAllocation(activity_type, Hours.from_value(hours))


def _day(
    weekday: Weekday,
    *activities: ActivityAllocation,
    cycle_week: int = 1,
) -> JobPlanDay:
    return JobPlanDay(cycle_week, weekday, activities)


def _blank_week(cycle_week: int = 1) -> list[JobPlanDay]:
    """Create the seven explicit day positions required by a cycle."""

    return [_day(weekday, cycle_week=cycle_week) for weekday in Weekday]


def _workbook_cycle() -> JobPlanCycle:
    """Build the standard pattern visible in the supplied workbook."""

    days = _blank_week()
    days[Weekday.MONDAY] = _day(
        Weekday.MONDAY,
        _activity(ActivityType.DCC, "8"),
        _activity(ActivityType.SPA, "0.5"),
    )
    days[Weekday.TUESDAY] = _day(
        Weekday.TUESDAY,
        _activity(ActivityType.DCC, "8"),
        _activity(ActivityType.SPA, "2"),
    )
    days[Weekday.WEDNESDAY] = _day(
        Weekday.WEDNESDAY,
        _activity(ActivityType.DCC, "4.5"),
        _activity(ActivityType.SPA, "1.5"),
    )

    return JobPlanCycle(
        week_count=1,
        contracted_pas=ProgrammedActivities.from_value("8.470"),
        dcc_pas=ProgrammedActivities.from_value("5.910"),
        spa_pas=ProgrammedActivities.from_value("2.560"),
        other_pas=ProgrammedActivities.from_value("0"),
        hours_per_pa=Hours.from_value("4"),
        days=tuple(days),
    )


def _version(
    *,
    version_id: str = "job-plan.reference",
    effective_from: date = date(2025, 8, 29),
    effective_to: date | None = None,
    anchor: date = date(2025, 8, 25),
    cycle: JobPlanCycle | None = None,
) -> JobPlanVersion:
    return JobPlanVersion(
        version_id=RuleId(version_id),
        effective_from=effective_from,
        effective_to=effective_to,
        cycle_anchor_date=anchor,
        cycle=cycle or _workbook_cycle(),
    )


def test_workbook_pa_split_reconciles_exactly() -> None:
    """5.910 DCC plus 2.560 SPA must equal the displayed 8.470 PAs."""

    cycle = _workbook_cycle()

    assert cycle.allocated_pas == ProgrammedActivities.from_value("8.470")
    assert cycle.reconciliation_variance == Decimal("0.000")
    assert cycle.is_reconciled
    assert cycle.pas_for(ActivityType.DCC).value == Decimal("5.910")
    assert cycle.pas_for(ActivityType.SPA).value == Decimal("2.560")
    assert cycle.pas_for(ActivityType.OTHER).value == Decimal("0")


def test_workbook_weekday_hours_remain_separate_from_contracted_pas() -> None:
    """Flexible activity means visible hours need not equal contracted hours."""

    cycle = _workbook_cycle()

    assert cycle.activity_hours(ActivityType.DCC) == Hours.from_value("20.5")
    assert cycle.activity_hours(ActivityType.SPA) == Hours.from_value("4.0")
    assert cycle.actual_cycle_hours == Hours.from_value("24.5")
    assert cycle.average_weekly_hours == Hours.from_value("24.5")
    assert cycle.scheduled_average_weekly_pas.value == Decimal("6.125")
    assert cycle.is_reconciled


def test_activity_proportions_use_the_contracted_pa_split() -> None:
    """Entitlement allocation follows 5.910/2.560, not visible daily hours."""

    cycle = _workbook_cycle()

    assert cycle.activity_proportion(ActivityType.DCC) == (Decimal("5.910") / Decimal("8.470"))
    assert cycle.activity_proportion(ActivityType.SPA) == (Decimal("2.560") / Decimal("8.470"))
    assert cycle.activity_proportion(ActivityType.OTHER) == Decimal("0")


def test_standard_day_returns_exact_dcc_and_spa_hours() -> None:
    monday = _workbook_cycle().day(1, Weekday.MONDAY)

    assert monday.total_hours == Hours.from_value("8.5")
    assert monday.hours_for(ActivityType.DCC) == Hours.from_value("8")
    assert monday.hours_for(ActivityType.SPA) == Hours.from_value("0.5")
    assert monday.hours_for(ActivityType.OTHER) == Hours.from_value("0")


def test_effective_version_maps_calendar_dates_to_weekdays() -> None:
    version = _version()

    monday = version.day_on(date(2025, 9, 1))
    thursday = version.day_on(date(2025, 9, 4))

    assert monday.weekday is Weekday.MONDAY
    assert monday.total_hours == Hours.from_value("8.5")
    assert thursday.weekday is Weekday.THURSDAY
    assert thursday.total_hours == Hours.from_value("0")


def test_two_week_cycle_repeats_from_a_monday_anchor() -> None:
    """Multi-week support adds week parity, not rota or shift behaviour."""

    days = _blank_week(1) + _blank_week(2)
    days[0] = _day(
        Weekday.MONDAY,
        _activity(ActivityType.DCC, "8"),
        cycle_week=1,
    )
    days[7] = _day(
        Weekday.MONDAY,
        _activity(ActivityType.SPA, "8"),
        cycle_week=2,
    )
    cycle = JobPlanCycle(
        week_count=2,
        contracted_pas=ProgrammedActivities.from_value("4"),
        dcc_pas=ProgrammedActivities.from_value("2"),
        spa_pas=ProgrammedActivities.from_value("2"),
        other_pas=ProgrammedActivities.from_value("0"),
        hours_per_pa=Hours.from_value("4"),
        days=tuple(days),
    )

    assert cycle.day_on(date(2025, 8, 25), cycle_anchor_date=date(2025, 8, 25)).hours_for(
        ActivityType.DCC
    ) == Hours.from_value("8")
    assert cycle.day_on(date(2025, 9, 1), cycle_anchor_date=date(2025, 8, 25)).hours_for(
        ActivityType.SPA
    ) == Hours.from_value("8")
    assert cycle.day_on(date(2025, 9, 8), cycle_anchor_date=date(2025, 8, 25)).hours_for(
        ActivityType.DCC
    ) == Hours.from_value("8")


def test_zero_pa_plan_has_zero_activity_proportions() -> None:
    cycle = JobPlanCycle(
        week_count=1,
        contracted_pas=ProgrammedActivities.from_value("0"),
        dcc_pas=ProgrammedActivities.from_value("0"),
        spa_pas=ProgrammedActivities.from_value("0"),
        other_pas=ProgrammedActivities.from_value("0"),
        hours_per_pa=Hours.from_value("4"),
        days=tuple(_blank_week()),
    )

    assert cycle.activity_proportion(ActivityType.DCC) == Decimal("0")


def test_pa_mismatch_requires_a_reason_but_daily_hours_do_not() -> None:
    cycle = _workbook_cycle()

    with pytest.raises(ValueError, match="do not reconcile"):
        replace(
            cycle,
            spa_pas=ProgrammedActivities.from_value("2.5"),
        )

    overridden = replace(
        cycle,
        spa_pas=ProgrammedActivities.from_value("2.5"),
        reconciliation_override_reason="Approved legacy job-plan variance",
    )
    assert not overridden.is_reconciled
    assert overridden.reconciliation_variance == Decimal("-0.060")


@pytest.mark.parametrize(
    ("changes", "error_type", "message"),
    [
        ({"activity_type": cast(Any, "dcc")}, TypeError, "ActivityType"),
        ({"hours": cast(Any, Decimal("8"))}, TypeError, "Hours"),
        ({"hours": Hours.from_value("0")}, ValueError, "greater than zero"),
        ({"hours": Hours.from_value("-1")}, ValueError, "greater than zero"),
    ],
)
def test_activity_allocation_validation(
    changes: dict[str, Any],
    error_type: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        replace(_activity(ActivityType.DCC, "8"), **changes)


@pytest.mark.parametrize(
    ("changes", "error_type", "message"),
    [
        ({"cycle_week": cast(Any, True)}, TypeError, "integer"),
        ({"cycle_week": 0}, ValueError, "at least one"),
        ({"weekday": cast(Any, 0)}, TypeError, "Weekday"),
        ({"activities": cast(Any, [])}, TypeError, "tuple"),
        ({"activities": cast(Any, ("bad",))}, TypeError, "ActivityAllocation"),
        (
            {
                "activities": (
                    _activity(ActivityType.DCC, "4"),
                    _activity(ActivityType.DCC, "4"),
                )
            },
            ValueError,
            "repeat",
        ),
    ],
)
def test_job_plan_day_validation(
    changes: dict[str, Any],
    error_type: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        replace(_day(Weekday.MONDAY), **changes)


def test_day_rejects_invalid_activity_lookup() -> None:
    with pytest.raises(TypeError, match="ActivityType"):
        _day(Weekday.MONDAY).hours_for(cast(Any, "dcc"))


@pytest.mark.parametrize(
    ("changes", "error_type", "message"),
    [
        ({"week_count": cast(Any, True)}, TypeError, "integer"),
        ({"week_count": 0}, ValueError, "at least one"),
        ({"contracted_pas": cast(Any, Decimal("8.47"))}, TypeError, "contracted_pas"),
        ({"dcc_pas": cast(Any, Decimal("5.91"))}, TypeError, "dcc_pas"),
        ({"spa_pas": cast(Any, Decimal("2.56"))}, TypeError, "spa_pas"),
        ({"other_pas": cast(Any, Decimal("0"))}, TypeError, "other_pas"),
        ({"hours_per_pa": cast(Any, Decimal("4"))}, TypeError, "hours_per_pa"),
        ({"hours_per_pa": Hours.from_value("0")}, ValueError, "greater than zero"),
        ({"days": cast(Any, [])}, TypeError, "tuple"),
        ({"days": cast(Any, ("bad",))}, TypeError, "JobPlanDay"),
        ({"reconciliation_override_reason": " "}, ValueError, "cannot be blank"),
    ],
)
def test_job_plan_cycle_field_validation(
    changes: dict[str, Any],
    error_type: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        replace(_workbook_cycle(), **changes)


def test_cycle_requires_every_position_once() -> None:
    cycle = _workbook_cycle()

    with pytest.raises(ValueError, match="exactly one record"):
        replace(cycle, days=cycle.days[:-1])
    with pytest.raises(ValueError, match="duplicate"):
        replace(cycle, days=(*cycle.days[:-1], cycle.days[0]))


def test_cycle_lookup_and_date_validation() -> None:
    cycle = _workbook_cycle()

    with pytest.raises(TypeError, match="ActivityType"):
        cycle.activity_hours(cast(Any, "dcc"))
    with pytest.raises(TypeError, match="ActivityType"):
        cycle.pas_for(cast(Any, "dcc"))
    with pytest.raises(LookupError, match="not found"):
        cycle.day(2, Weekday.MONDAY)
    with pytest.raises(TypeError, match="Target date"):
        cycle.day_on(cast(Any, datetime(2025, 8, 25)), cycle_anchor_date=date(2025, 8, 25))
    with pytest.raises(TypeError, match="anchor date"):
        cycle.day_on(date(2025, 8, 25), cycle_anchor_date=cast(Any, datetime(2025, 8, 25)))
    with pytest.raises(ValueError, match="Monday"):
        cycle.day_on(date(2025, 8, 25), cycle_anchor_date=date(2025, 8, 26))


@pytest.mark.parametrize(
    ("changes", "error_type", "message"),
    [
        ({"version_id": cast(Any, "bad")}, TypeError, "version_id"),
        ({"effective_from": cast(Any, datetime(2025, 8, 29))}, TypeError, "effective_from"),
        ({"effective_to": cast(Any, datetime(2026, 1, 1))}, TypeError, "effective_to"),
        ({"effective_to": date(2025, 8, 28)}, ValueError, "before"),
        ({"cycle_anchor_date": cast(Any, datetime(2025, 8, 25))}, TypeError, "anchor"),
        ({"cycle_anchor_date": date(2025, 8, 26)}, ValueError, "Monday"),
        ({"cycle_anchor_date": date(2025, 9, 1)}, ValueError, "after"),
        ({"cycle": cast(Any, "bad")}, TypeError, "JobPlanCycle"),
    ],
)
def test_job_plan_version_validation(
    changes: dict[str, Any],
    error_type: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        replace(_version(), **changes)


def test_version_effective_boundaries_and_invalid_dates() -> None:
    version = _version(effective_to=date(2026, 8, 1))

    assert version.includes(date(2025, 8, 29))
    assert version.includes(date(2026, 8, 1))
    assert not version.includes(date(2026, 8, 2))
    with pytest.raises(TypeError, match="Target date"):
        version.includes(cast(Any, datetime(2025, 8, 29)))
    with pytest.raises(ValueError, match="does not apply"):
        version.day_on(date(2026, 8, 2))


def test_history_selects_adjacent_job_plan_versions() -> None:
    first = _version(effective_to=date(2026, 7, 31))
    second = _version(
        version_id="job-plan.reference.2",
        effective_from=date(2026, 8, 1),
        anchor=date(2026, 7, 27),
    )
    history = JobPlanHistory((first, second))

    assert history.version_on(date(2026, 7, 31)) is first
    assert history.version_on(date(2026, 8, 1)) is second
    assert history.day_on(date(2026, 8, 3)).weekday is Weekday.MONDAY


def test_history_validation_and_gaps() -> None:
    first = _version(effective_to=date(2026, 7, 31))
    second = _version(
        version_id="job-plan.reference.2",
        effective_from=date(2026, 8, 2),
        anchor=date(2026, 7, 27),
    )

    with pytest.raises(TypeError, match="tuple"):
        JobPlanHistory(cast(Any, []))
    with pytest.raises(ValueError, match="at least one"):
        JobPlanHistory(())
    with pytest.raises(TypeError, match="JobPlanVersion"):
        JobPlanHistory(cast(Any, ("bad",)))
    with pytest.raises(ValueError, match="chronological"):
        JobPlanHistory((second, first))
    with pytest.raises(ValueError, match="overlap"):
        JobPlanHistory((first, _version(version_id="job-plan.overlap")))

    history = JobPlanHistory((first, second))
    with pytest.raises(LookupError, match="exactly one"):
        history.version_on(date(2026, 8, 1))
