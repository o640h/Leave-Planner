"""Editable leave records and their calculated outputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from annual_entitlement import AppliedEntitlement
from domain import (
    ZERO_HOURS,
    DateRange,
    Hours,
    LeaveState,
    ProgrammedActivities,
    RuleId,
)
from job_plans import JobPlanHistory
from public_holidays import PublicHolidayResult


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

    def scale(self, factor: Decimal) -> ActivityHours:
        """Scale every activity while preserving the DCC/SPA/Other split."""

        return ActivityHours(
            dcc=self.dcc.scale(factor),
            spa=self.spa.scale(factor),
            other=self.other.scale(factor),
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
    reason: str | None = None
    dcc_hours: Hours | None = None
    spa_hours: Hours | None = None
    other_hours: Hours | None = None

    def __post_init__(self) -> None:
        if self.reason is not None:
            object.__setattr__(self, "reason", self.reason.strip() or None)

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
    """One booking date with entered hours and its calculation metadata."""

    booking_id: str
    leave_date: date
    state: LeaveState
    job_plan_version: RuleId
    standard_hours: ActivityHours
    deduction_hours: ActivityHours
    override_reason: str | None = None
    contracted_pas: ProgrammedActivities | None = None
    deduction_factor: Decimal | None = None

    @property
    def is_overridden(self) -> bool:
        return self.override_reason is not None

    @property
    def calculated_deduction_hours(self) -> ActivityHours:
        """Apply the dated PA cap without changing the entered daily hours."""

        return self.deduction_hours.scale(self.deduction_factor or Decimal("1"))


@dataclass(frozen=True, slots=True)
class CarryForward:
    """Approved carry-forward added to the opening balance."""

    carry_forward_id: str
    effective_date: date
    hours: ActivityHours

    def __post_init__(self) -> None:
        if not self.carry_forward_id.strip():
            raise ValueError("Carry-forward ID cannot be empty")

        if self.hours.is_zero:
            raise ValueError("Carry-forward hours cannot all be zero")

        if self.hours.has_negative_value:
            raise ValueError("Carry-forward hours cannot be negative")


@dataclass(frozen=True, slots=True)
class BalanceView:
    """A traceable balance for one lifecycle view."""

    basis: BalanceBasis
    opening_entitlement: ActivityHours
    carry_forward: ActivityHours
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
    carry_forward: tuple[CarryForward, ...] = ()

    def __post_init__(self) -> None:
        booking_ids = tuple(booking.booking_id for booking in self.bookings)
        if len(booking_ids) != len(set(booking_ids)):
            raise ValueError("Booking IDs must be unique")

        if any(
            booking.period.start not in self.leave_year or booking.period.end not in self.leave_year
            for booking in self.bookings
        ):
            raise ValueError("Every booking must fall inside the leave year")

        carry_forward_ids = tuple(item.carry_forward_id for item in self.carry_forward)
        if len(carry_forward_ids) != len(set(carry_forward_ids)):
            raise ValueError("Carry-forward IDs must be unique")

        if any(item.effective_date not in self.leave_year for item in self.carry_forward):
            raise ValueError("Carry-forward must fall inside the leave year")


@dataclass(frozen=True, slots=True)
class LeaveRecordsResult:
    """Expanded leave days and all three balance views."""

    days: tuple[LeaveDay, ...]
    carry_forward: tuple[CarryForward, ...]
    projected: BalanceView
    confirmed: BalanceView
    actual: BalanceView
