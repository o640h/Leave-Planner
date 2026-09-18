"""Tests for the calculation engine's shared domain contracts.

These tests concentrate on invariants that every later entitlement and leave
calculation will rely on: exact arithmetic, unambiguous dates, stable codes,
and immutable audit information.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from domain import (
    ZERO_HOURS,
    ActivityType,
    CalculationResult,
    CalculationStep,
    CalculationWarning,
    DateRange,
    Hours,
    LeaveState,
    RuleId,
    WarningSeverity,
)


def test_hours_use_exact_decimal_arithmetic() -> None:
    """Values such as 0.1 and 0.2 must add exactly, unlike binary floats."""
    result = Hours.from_value("0.1") + Hours.from_value("0.2")

    assert result == Hours(Decimal("0.3"))
    assert str(result) == "0.3"


@pytest.mark.parametrize("unsafe_value", [0.1, True, False])
def test_hours_reject_binary_floats_and_booleans(unsafe_value: Any) -> None:
    """A float or boolean entering here would undermine every later total."""
    with pytest.raises(TypeError, match="bool or float"):
        Hours.from_value(unsafe_value)


@pytest.mark.parametrize("non_finite", [Decimal("NaN"), Decimal("Infinity")])
def test_hours_reject_non_finite_decimals(non_finite: Decimal) -> None:
    with pytest.raises(ValueError, match="finite"):
        Hours(non_finite)


def test_hours_support_exact_proration_ratios_and_signed_deltas() -> None:
    """Signed values support balance maths; scaling supports LTFT work."""
    entitlement = Hours.from_value("40")
    delta = Hours.from_value("-1.25")

    assert entitlement.scale("0.6") == Hours.from_value("24.0")
    assert Hours.from_value("6").ratio_of(entitlement) == Decimal("0.15")
    assert entitlement + delta == Hours.from_value("38.75")
    assert -delta == Hours.from_value("1.25")
    assert Hours.from_value("0") == ZERO_HOURS


def test_hours_ratio_rejects_a_zero_total() -> None:
    with pytest.raises(ZeroDivisionError, match="zero hours"):
        Hours.from_value("1").ratio_of(ZERO_HOURS)


# This property test exercises many values rather than relying only on a few
# examples. It protects the core promise that Hours arithmetic equals Decimal
# arithmetic exactly and is commutative for addition.
finite_three_place_decimals = st.decimals(
    min_value=Decimal("-10000"),
    max_value=Decimal("10000"),
    allow_nan=False,
    allow_infinity=False,
    places=3,
)


@given(left=finite_three_place_decimals, right=finite_three_place_decimals)
def test_hours_addition_matches_decimal_addition(left: Decimal, right: Decimal) -> None:
    left_hours = Hours(left)
    right_hours = Hours(right)

    assert left_hours + right_hours == Hours(left + right)
    assert left_hours + right_hours == right_hours + left_hours


def test_date_range_is_inclusive_and_handles_a_leap_day() -> None:
    """A booking range must emit every calendar date, including 29 February."""
    period = DateRange(date(2024, 2, 28), date(2024, 3, 1))

    assert period.calendar_days == 3
    assert list(period.dates()) == [
        date(2024, 2, 28),
        date(2024, 2, 29),
        date(2024, 3, 1),
    ]
    assert date(2024, 2, 29) in period
    assert date(2024, 3, 2) not in period


def test_date_range_rejects_reverse_ranges_and_datetimes() -> None:
    with pytest.raises(ValueError, match="before start"):
        DateRange(date(2026, 8, 2), date(2026, 8, 1))

    # The cast satisfies static typing while deliberately exercising malformed
    # runtime input from a future API or persistence boundary.
    datetime_boundary = cast(date, datetime(2026, 8, 1, 9, 30))
    with pytest.raises(TypeError, match="not datetimes"):
        DateRange(datetime_boundary, date(2026, 8, 2))


def test_domain_enums_have_stable_serialized_values() -> None:
    assert [activity.value for activity in ActivityType] == ["dcc", "spa", "other"]
    assert [state.value for state in LeaveState] == [
        "requested",
        "approved",
        "cancelled",
    ]
    assert [severity.value for severity in WarningSeverity] == ["info", "warning"]


@pytest.mark.parametrize(
    "identifier",
    ["entitlement.base", "public-holiday.accrual", "job_plan.reconciliation"],
)
def test_rule_id_accepts_clear_namespaced_identifiers(identifier: str) -> None:
    assert str(RuleId(identifier)) == identifier


@pytest.mark.parametrize(
    "identifier",
    ["", "Uppercase", "has spaces", ".leading", "two..dots"],
)
def test_rule_id_rejects_ambiguous_identifiers(identifier: str) -> None:
    with pytest.raises(ValueError, match="RuleId"):
        RuleId(identifier)


def test_warning_copies_and_freezes_its_context() -> None:
    """Audit metadata must not change when a caller mutates its source dict."""
    source_context = {"contracted_hours": "40", "planned_hours": "38.5"}
    warning = CalculationWarning(
        rule_id=RuleId("job-plan.reconciliation"),
        message="Job-plan hours do not reconcile",
        affected_period=DateRange(date(2026, 8, 1), date(2027, 7, 31)),
        context=source_context,
    )

    source_context["planned_hours"] = "40"

    assert warning.context["planned_hours"] == "38.5"
    mutable_view = cast(dict[str, str], warning.context)
    with pytest.raises(TypeError):
        mutable_view["planned_hours"] = "changed"


def test_warning_rejects_a_blank_explanation() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        CalculationWarning(rule_id=RuleId("quality.example"), message="   ")


def test_calculation_result_keeps_value_warnings_and_trace_together() -> None:
    """A result should carry enough evidence to explain how its value arose."""
    warning = CalculationWarning(
        rule_id=RuleId("quality.example"),
        message="Example warning",
        severity=WarningSeverity.INFO,
    )
    step = CalculationStep(
        rule_id=RuleId("entitlement.base"),
        description="Apply the base entitlement",
        amount=Hours.from_value("240"),
        effective_date=date(2026, 8, 1),
        context={"source": "HR.78"},
    )
    result: CalculationResult[Hours] = CalculationResult(
        value=Hours.from_value("240"),
        warnings=(warning,),
        trace=(step,),
    )

    assert result.value == Hours.from_value("240")
    assert result.warnings == (warning,)
    assert result.trace == (step,)
    assert result.has_warnings


def test_calculation_result_without_warnings_reports_false() -> None:
    result: CalculationResult[Hours] = CalculationResult(value=ZERO_HOURS)

    assert not result.has_warnings
