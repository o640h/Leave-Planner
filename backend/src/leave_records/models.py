"""Editable leave records and their calculated outputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from annual_entitlement import AppliedEntitlement
from domain import (
    ZERO_HOURS,
    DateRange,
    Hours,
    LeaveState,
    RuleId,
)
from job_plans import JobPlanHistory
from public_holidays import PublicHolidayResult


class AdjustmentKind(StrEnum):
    """Supported changes to available leave."""

    CARRY_FORWARD = "carry_forward"
    SOLD_LEAVE = "sold_leave"
    CORRECTION = "correction"


class BalanceBasis(StrEnum):
    """The booking states represented by a balance."""

    PROJECTED = "projected"
    CONFIRMED = "confirmed"
    ACTUAL = "actual"


@dataclass(frozen=True, slots=True)
class ActivityHours:
    """DCC, SPA, and Other hours kept together."""

    dcc: Hours = ZERO_HOURS
    spa: Hours = ZERO_HOURS
    other: Hours = ZERO_HOURS

    def __add__(self, other: ActivityHours) -> ActivityHours:
        return ActivityHours(
            dcc=self.dcc + other.dcc,
            spa=self.spa + other.spa,
            other=self.other + other.other,
        )

    def __sub__(self, other: ActivityHours) -> ActivityHours:
        return ActivityHours(
            dcc=self.dcc - other.dcc,
            spa=self.spa - other.spa,
            other=self.other - other.other,
        )

    @property
    def total(self) -> Hours:
        return self.dcc + self.spa + self.other

    @property
    def is_zero(self) -> bool:
        return self.dcc == self.spa == self.other == ZERO_HOURS

    @property
    def has_negative_value(self) -> bool:
        return any(value.value < 0 for value in (self.dcc, self.spa, self.other))

    @property
    def has_positive_value(self) -> bool:
        return any(value.value > 0 for value in (self.dcc, self.spa, self.other))


ZERO_ACTIVITY_HOURS = ActivityHours()


@dataclass(frozen=True, slots=True)
class DailyLeaveOverride:
    """Operator-entered replacement for part or all of one day."""

    leave_date: date
    reason: str
    dcc_hours: Hours | None = None
    spa_hours: Hours | None = None
    other_hours: Hours | None = None

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("Override reason cannot be empty")

        supplied_values = (
            self.dcc_hours,
            self.spa_hours,
            self.other_hours,
        )
        if all(value is None for value in supplied_values):
            raise ValueError("An override must replace at least one value")

        for value in supplied_values:
            if value is not None and value.value < 0:
                raise ValueError("Override values cannot be negative")

    def apply(self, standard: ActivityHours) -> ActivityHours:
        """Replace supplied fields and preserve the others."""

        return ActivityHours(
            dcc=(self.dcc_hours if self.dcc_hours is not None else standard.dcc),
            spa=(self.spa_hours if self.spa_hours is not None else standard.spa),
            other=(self.other_hours if self.other_hours is not None else standard.other),
        )


@dataclass(frozen=True, slots=True)
class LeaveBooking:
    """One operator-entered leave request."""

    booking_id: str
    period: DateRange
    state: LeaveState
    overrides: tuple[DailyLeaveOverride, ...] = ()
    note: str | None = None

    def __post_init__(self) -> None:
        if not self.booking_id.strip():
            raise ValueError("Booking ID cannot be empty")

        override_dates = tuple(override.leave_date for override in self.overrides)
        if len(override_dates) != len(set(override_dates)):
            raise ValueError("A booking cannot contain multiple overrides for one date")

        if any(override_date not in self.period for override_date in override_dates):
            raise ValueError("Every override must fall inside the booking period")

        if self.note is not None and not self.note.strip():
            raise ValueError("Booking note cannot be blank")


@dataclass(frozen=True, slots=True)
class LeaveDay:
    """One calculated date generated from a booking."""

    booking_id: str
    leave_date: date
    state: LeaveState
    job_plan_version: RuleId
    standard_hours: ActivityHours
    deduction_hours: ActivityHours
    override_reason: str | None = None

    @property
    def is_overridden(self) -> bool:
        return self.override_reason is not None


@dataclass(frozen=True, slots=True)
class LeaveAdjustment:
    """An explicit change to available leave hours."""

    adjustment_id: str
    effective_date: date
    kind: AdjustmentKind
    hours: ActivityHours
    reason: str

    def __post_init__(self) -> None:
        if not self.adjustment_id.strip():
            raise ValueError("Adjustment ID cannot be empty")

        if self.hours.is_zero:
            raise ValueError("Adjustment hours cannot all be zero")

        if not self.reason.strip():
            raise ValueError("Adjustment reason cannot be empty")

        if self.kind is AdjustmentKind.CARRY_FORWARD and self.hours.has_negative_value:
            raise ValueError("Carry-forward hours cannot be negative")

        if self.kind is AdjustmentKind.SOLD_LEAVE and self.hours.has_positive_value:
            raise ValueError("Sold-leave hours must be negative")


@dataclass(frozen=True, slots=True)
class BalanceView:
    """A traceable balance for one lifecycle view."""

    basis: BalanceBasis
    opening_entitlement: ActivityHours
    adjustments: ActivityHours
    public_holiday_deductions: ActivityHours
    booking_deductions: ActivityHours
    remaining: ActivityHours


@dataclass(frozen=True, slots=True)
class LeaveRecordsRequest:
    """Inputs required to calculate one consultant leave year."""

    leave_year: DateRange
    entitlement: AppliedEntitlement
    public_holidays: PublicHolidayResult
    job_plans: JobPlanHistory
    bookings: tuple[LeaveBooking, ...] = ()
    adjustments: tuple[LeaveAdjustment, ...] = ()

    def __post_init__(self) -> None:
        booking_ids = tuple(booking.booking_id for booking in self.bookings)
        if len(booking_ids) != len(set(booking_ids)):
            raise ValueError("Booking IDs must be unique")

        if any(
            booking.period.start not in self.leave_year or booking.period.end not in self.leave_year
            for booking in self.bookings
        ):
            raise ValueError("Every booking must fall inside the leave year")

        adjustment_ids = tuple(adjustment.adjustment_id for adjustment in self.adjustments)
        if len(adjustment_ids) != len(set(adjustment_ids)):
            raise ValueError("Adjustment IDs must be unique")

        if any(adjustment.effective_date not in self.leave_year for adjustment in self.adjustments):
            raise ValueError("Every adjustment must fall inside the leave year")


@dataclass(frozen=True, slots=True)
class LeaveRecordsResult:
    """Expanded leave days and all three balance views."""

    days: tuple[LeaveDay, ...]
    adjustments: tuple[LeaveAdjustment, ...]
    projected: BalanceView
    confirmed: BalanceView
    actual: BalanceView
