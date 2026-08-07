"""Leave-record expansion and balance calculation."""

from __future__ import annotations

from collections.abc import Iterable

from domain import (
    CalculationResult,
    CalculationStep,
    LeaveState,
    RuleId,
)

from .expansion import expand_booking
from .models import (
    ZERO_ACTIVITY_HOURS,
    ActivityHours,
    BalanceBasis,
    BalanceView,
    LeaveDay,
    LeaveRecordsRequest,
    LeaveRecordsResult,
)
from .warnings import evaluate_leave_warnings

_PROJECTED_STATES = {
    LeaveState.PLANNED,
    LeaveState.APPROVED,
    LeaveState.TAKEN,
}
_CONFIRMED_STATES = {
    LeaveState.APPROVED,
    LeaveState.TAKEN,
}
_ACTUAL_STATES = {
    LeaveState.TAKEN,
}


def _sum_hours(
    values: Iterable[ActivityHours],
) -> ActivityHours:
    total = ZERO_ACTIVITY_HOURS

    for value in values:
        total += value

    return total


def _opening_entitlement(
    request: LeaveRecordsRequest,
) -> ActivityHours:
    """Combine policy and public-holiday entitlement."""

    return ActivityHours(
        dcc=(request.entitlement.dcc_hours + request.public_holidays.dcc_entitlement_hours),
        spa=(request.entitlement.spa_hours + request.public_holidays.spa_entitlement_hours),
        other=(request.entitlement.other_hours + request.public_holidays.other_entitlement_hours),
    )


def _public_holiday_deductions(
    request: LeaveRecordsRequest,
) -> ActivityHours:
    return _sum_hours(
        ActivityHours(
            dcc=occurrence.dcc_deduction_hours,
            spa=occurrence.spa_deduction_hours,
            other=occurrence.other_deduction_hours,
        )
        for occurrence in request.public_holidays.occurrences
    )


def _booking_deductions(
    days: tuple[LeaveDay, ...],
    included_states: set[LeaveState],
) -> ActivityHours:
    return _sum_hours(day.deduction_hours for day in days if day.state in included_states)


def _balance_view(
    *,
    basis: BalanceBasis,
    opening_entitlement: ActivityHours,
    adjustments: ActivityHours,
    public_holiday_deductions: ActivityHours,
    booking_deductions: ActivityHours,
) -> BalanceView:
    remaining = opening_entitlement + adjustments - public_holiday_deductions - booking_deductions

    return BalanceView(
        basis=basis,
        opening_entitlement=opening_entitlement,
        adjustments=adjustments,
        public_holiday_deductions=(public_holiday_deductions),
        booking_deductions=booking_deductions,
        remaining=remaining,
    )


def calculate_leave_records(
    request: LeaveRecordsRequest,
) -> CalculationResult[LeaveRecordsResult]:
    """Expand all bookings and derive lifecycle balances."""

    if not isinstance(request, LeaveRecordsRequest):
        raise TypeError("request must be a LeaveRecordsRequest")

    days = tuple(
        day
        for booking in request.bookings
        for day in expand_booking(
            booking,
            request.job_plans,
        )
    )
    adjustments = _sum_hours(adjustment.hours for adjustment in request.adjustments)
    opening = _opening_entitlement(request)
    holiday_deductions = _public_holiday_deductions(request)

    projected = _balance_view(
        basis=BalanceBasis.PROJECTED,
        opening_entitlement=opening,
        adjustments=adjustments,
        public_holiday_deductions=holiday_deductions,
        booking_deductions=_booking_deductions(
            days,
            _PROJECTED_STATES,
        ),
    )
    confirmed = _balance_view(
        basis=BalanceBasis.CONFIRMED,
        opening_entitlement=opening,
        adjustments=adjustments,
        public_holiday_deductions=holiday_deductions,
        booking_deductions=_booking_deductions(
            days,
            _CONFIRMED_STATES,
        ),
    )
    actual = _balance_view(
        basis=BalanceBasis.ACTUAL,
        opening_entitlement=opening,
        adjustments=adjustments,
        public_holiday_deductions=holiday_deductions,
        booking_deductions=_booking_deductions(
            days,
            _ACTUAL_STATES,
        ),
    )

    result = LeaveRecordsResult(
        days=days,
        adjustments=request.adjustments,
        projected=projected,
        confirmed=confirmed,
        actual=actual,
    )

    day_trace = tuple(
        CalculationStep(
            rule_id=RuleId("leave-records.daily-deduction"),
            description=("Expanded a booking date using the effective job plan"),
            amount=day.deduction_hours.total,
            effective_date=day.leave_date,
            context={
                "booking_id": day.booking_id,
                "state": day.state.value,
                "job_plan_version": str(day.job_plan_version),
                "dcc_hours": str(day.deduction_hours.dcc),
                "spa_hours": str(day.deduction_hours.spa),
                "other_hours": str(day.deduction_hours.other),
                "overridden": str(day.is_overridden).lower(),
            },
        )
        for day in days
    )

    adjustment_trace = tuple(
        CalculationStep(
            rule_id=RuleId(f"leave-adjustment.{adjustment.kind.value}"),
            description=("Applied an operator-entered leave adjustment"),
            amount=adjustment.hours.total,
            effective_date=adjustment.effective_date,
            context={
                "adjustment_id": (adjustment.adjustment_id),
                "reason": adjustment.reason,
                "dcc_hours": str(adjustment.hours.dcc),
                "spa_hours": str(adjustment.hours.spa),
                "other_hours": str(adjustment.hours.other),
            },
        )
        for adjustment in request.adjustments
    )

    balance_trace = tuple(
        CalculationStep(
            rule_id=RuleId(f"leave-balance.{view.basis.value}"),
            description=(f"Calculated {view.basis.value} remaining leave"),
            amount=view.remaining.total,
            context={
                "remaining_dcc": str(view.remaining.dcc),
                "remaining_spa": str(view.remaining.spa),
                "remaining_other": str(view.remaining.other),
                "booking_deductions": str(view.booking_deductions.total),
                "public_holiday_deductions": str(view.public_holiday_deductions.total),
            },
        )
        for view in (
            projected,
            confirmed,
            actual,
        )
    )

    return CalculationResult(
        value=result,
        warnings=evaluate_leave_warnings(
            request,
            result,
        ),
        trace=(day_trace + adjustment_trace + balance_trace),
    )
