"""Inputs and outputs for annual leave calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from domain import ZERO_HOURS, DateRange, Hours, RuleId
from entitlement_policy import EntitlementPolicyCatalogue
from job_plans import JobPlanHistory


@dataclass(frozen=True, slots=True)
class LeaveCalculationRequest:
    """Information required to calculate one consultant leave year."""

    leave_year: DateRange
    employment_start: date
    employment_end: date | None
    consultant_appointment_date: date
    consultant_service_start_date: date
    policies: EntitlementPolicyCatalogue
    job_plans: JobPlanHistory

    def __post_init__(self) -> None:
        if self.employment_end is not None and self.employment_end < self.employment_start:
            raise ValueError("employment_end cannot be before employment_start")

    @property
    def active_period(self) -> DateRange | None:
        """Return employment clipped to the requested leave year."""

        start = max(self.leave_year.start, self.employment_start)
        end = min(self.leave_year.end, self.employment_end or self.leave_year.end)

        if end < start:
            return None

        return DateRange(start, end)


@dataclass(frozen=True, slots=True)
class LeaveCalculationPeriod:
    """One period during which all entitlement inputs are constant."""

    period: DateRange
    completed_service_years: int
    policy_version: str
    job_plan_version: RuleId
    year_fraction: Decimal
    full_year_hours: Hours
    entitlement_hours: Hours
    dcc_hours: Hours
    spa_hours: Hours
    other_hours: Hours

    def __post_init__(self) -> None:
        if self.completed_service_years < 0:
            raise ValueError("Completed service years cannot be negative")
        if not self.policy_version.strip():
            raise ValueError("Policy version cannot be empty")
        if not Decimal("0") <= self.year_fraction <= Decimal("1"):
            raise ValueError("Year fraction must be between zero and one")


@dataclass(frozen=True, slots=True)
class LeaveCalculationResult:
    """All calculation periods and their derived totals."""

    leave_year: DateRange
    active_period: DateRange | None
    periods: tuple[LeaveCalculationPeriod, ...]

    @property
    def entitlement_hours(self) -> Hours:
        return self._sum("entitlement_hours")

    @property
    def dcc_hours(self) -> Hours:
        return self._sum("dcc_hours")

    @property
    def spa_hours(self) -> Hours:
        return self._sum("spa_hours")

    @property
    def other_hours(self) -> Hours:
        return self._sum("other_hours")

    def _sum(self, field_name: str) -> Hours:
        total = ZERO_HOURS

        for period in self.periods:
            total += getattr(period, field_name)

        return total
