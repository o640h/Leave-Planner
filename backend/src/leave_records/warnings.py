"""Non-blocking warnings derived from calculated leave records."""

from __future__ import annotations

from datetime import date

from domain import (
    CalculationWarning,
    DateRange,
    LeaveState,
    RuleId,
    WarningSeverity,
)

from .models import (
    ZERO_ACTIVITY_HOURS,
    ActivityHours,
    AdjustmentKind,
    BalanceView,
    LeaveBooking,
    LeaveRecordsRequest,
    LeaveRecordsResult,
)

_ACTIVE_BOOKING_STATES = frozenset(
    {
        LeaveState.PLANNED,
        LeaveState.APPROVED,
        LeaveState.TAKEN,
    }
)


def _overlapping_period(
    first: DateRange,
    second: DateRange,
) -> DateRange | None:
    """Return the shared portion of two date ranges."""

    start = max(first.start, second.start)
    end = min(first.end, second.end)

    if end < start:
        return None

    return DateRange(start, end)


def _booking_overlap_warnings(
    bookings: tuple[LeaveBooking, ...],
) -> tuple[CalculationWarning, ...]:
    """Warn when two active bookings include the same dates."""

    active_bookings = tuple(
        booking for booking in bookings if booking.state in _ACTIVE_BOOKING_STATES
    )
    warnings: list[CalculationWarning] = []

    for index, first in enumerate(active_bookings):
        for second in active_bookings[index + 1 :]:
            overlap = _overlapping_period(
                first.period,
                second.period,
            )

            if overlap is None:
                continue

            warnings.append(
                CalculationWarning(
                    rule_id=RuleId("leave-records.overlapping-bookings"),
                    message=(
                        "Two active leave bookings overlap. "
                        "Check that the same leave has not been "
                        "entered twice."
                    ),
                    affected_period=overlap,
                    context={
                        "first_booking_id": first.booking_id,
                        "first_state": first.state.value,
                        "second_booking_id": second.booking_id,
                        "second_state": second.state.value,
                    },
                )
            )

    return tuple(warnings)


def _remaining_context(
    remaining: ActivityHours,
) -> dict[str, str]:
    """Create consistent warning details for a balance."""

    return {
        "remaining_dcc": str(remaining.dcc),
        "remaining_spa": str(remaining.spa),
        "remaining_other": str(remaining.other),
        "remaining_total": str(remaining.total),
    }


def _balance_warning(
    view: BalanceView,
    leave_year: DateRange,
) -> CalculationWarning | None:
    """Warn when a balance is overdrawn or uneven by activity."""

    remaining = view.remaining

    if not remaining.has_negative_value:
        return None

    if remaining.total.value < 0:
        return CalculationWarning(
            rule_id=RuleId(f"leave-balance.overdrawn.{view.basis.value}"),
            message=(f"The {view.basis.value} leave balance is overdrawn overall."),
            affected_period=leave_year,
            context=_remaining_context(remaining),
        )

    return CalculationWarning(
        rule_id=RuleId(f"leave-balance.activity-imbalance.{view.basis.value}"),
        message=(
            f"The {view.basis.value} balance has enough hours "
            "overall, but one or more activity balances are negative."
        ),
        affected_period=leave_year,
        context=_remaining_context(remaining),
    )


def _balance_warnings(
    result: LeaveRecordsResult,
    leave_year: DateRange,
) -> tuple[CalculationWarning, ...]:
    """Check projected, confirmed, and actual balances."""

    warnings: list[CalculationWarning] = []

    for view in (
        result.projected,
        result.confirmed,
        result.actual,
    ):
        warning = _balance_warning(view, leave_year)

        if warning is not None:
            warnings.append(warning)

    return tuple(warnings)


def _effective_period(
    *,
    effective_from: date,
    effective_to: date | None,
    leave_year: DateRange,
) -> DateRange | None:
    """Clip an effective-dated record to the leave year."""

    start = max(effective_from, leave_year.start)
    end = min(
        effective_to or leave_year.end,
        leave_year.end,
    )

    if end < start:
        return None

    return DateRange(start, end)


def _job_plan_warnings(
    request: LeaveRecordsRequest,
) -> tuple[CalculationWarning, ...]:
    """Expose job plans saved with a reconciliation override."""

    warnings: list[CalculationWarning] = []

    for version in request.job_plans.versions:
        affected_period = _effective_period(
            effective_from=version.effective_from,
            effective_to=version.effective_to,
            leave_year=request.leave_year,
        )

        if affected_period is None or version.cycle.is_reconciled:
            continue

        warnings.append(
            CalculationWarning(
                rule_id=RuleId("job-plan.reconciliation-override"),
                message=(
                    "The job-plan activity split does not match "
                    "the total contracted PAs. An operator override "
                    "is being used."
                ),
                affected_period=affected_period,
                context={
                    "job_plan_version": str(version.version_id),
                    "contracted_pas": str(version.cycle.contracted_pas),
                    "allocated_pas": str(version.cycle.allocated_pas),
                    "variance": str(version.cycle.reconciliation_variance),
                    "override_reason": (version.cycle.reconciliation_override_reason or ""),
                },
            )
        )

    return tuple(warnings)


def _carry_forward_warning(
    request: LeaveRecordsRequest,
) -> CalculationWarning | None:
    """Surface carry-forward without inventing an expiry rule."""

    carry_forward = ZERO_ACTIVITY_HOURS

    for adjustment in request.adjustments:
        if adjustment.kind is AdjustmentKind.CARRY_FORWARD:
            carry_forward += adjustment.hours

    if carry_forward.is_zero:
        return None

    return CalculationWarning(
        rule_id=RuleId("leave-adjustment.carry-forward"),
        message=(
            "Carry-forward is included in this leave year. "
            "Confirm that its approval and use comply with the "
            "applicable local policy."
        ),
        severity=WarningSeverity.INFO,
        affected_period=request.leave_year,
        context={
            "dcc_hours": str(carry_forward.dcc),
            "spa_hours": str(carry_forward.spa),
            "other_hours": str(carry_forward.other),
            "total_hours": str(carry_forward.total),
        },
    )


def evaluate_leave_warnings(
    request: LeaveRecordsRequest,
    result: LeaveRecordsResult,
) -> tuple[CalculationWarning, ...]:
    """Return deterministic, non-blocking leave warnings."""

    if not isinstance(request, LeaveRecordsRequest):
        raise TypeError("request must be a LeaveRecordsRequest")

    if not isinstance(result, LeaveRecordsResult):
        raise TypeError("result must be a LeaveRecordsResult")

    carry_forward_warning = _carry_forward_warning(request)

    return (
        _booking_overlap_warnings(request.bookings)
        + _balance_warnings(result, request.leave_year)
        + _job_plan_warnings(request)
        + ((carry_forward_warning,) if carry_forward_warning is not None else ())
    )
