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
        if not isinstance(self.leave_year, DateRange):
            raise TypeError("leave_year must be a DateRange")

        for field_name, value in (
            ("employment_start", self.employment_start),
            ("consultant_appointment_date", self.consultant_appointment_date),
            ("consultant_service_start_date", self.consultant_service_start_date),
        ):
            if type(value) is not date:
                raise TypeError(f"{field_name} must be a date")

        if self.employment_end is not None and type(self.employment_end) is not date:
            raise TypeError("employment_end must be a date")

        if self.employment_end is not None and self.employment_end < self.employment_start:
            raise ValueError("employment_end cannot be before employment_start")

        if not isinstance(self.policies, EntitlementPolicyCatalogue):
            raise TypeError("policies must be an EntitlementPolicyCatalogue")

        if not isinstance(self.job_plans, JobPlanHistory):
            raise TypeError("job_plans must be a JobPlanHistory")

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
        if not isinstance(self.period, DateRange):
            raise TypeError("Calculation period must be a DateRange")

        if isinstance(self.completed_service_years, bool) or not isinstance(
            self.completed_service_years, int
        ):
            raise TypeError("Completed service years must be an integer")

        if self.completed_service_years < 0:
            raise ValueError("Completed service years cannot be negative")

        if not isinstance(self.policy_version, str) or not self.policy_version.strip():
            raise ValueError("Policy version cannot be empty")

        if not isinstance(self.job_plan_version, RuleId):
            raise TypeError("Job-plan version must be a RuleId")

        if not isinstance(self.year_fraction, Decimal):
            raise TypeError("Year fraction must be a Decimal")

        if not self.year_fraction.is_finite():
            raise ValueError("Year fraction must be finite")

        if not Decimal("0") <= self.year_fraction <= Decimal("1"):
            raise ValueError("Year fraction must be between zero and one")

        for field_name, value in (
            ("full_year_hours", self.full_year_hours),
            ("entitlement_hours", self.entitlement_hours),
            ("dcc_hours", self.dcc_hours),
            ("spa_hours", self.spa_hours),
            ("other_hours", self.other_hours),
        ):
            if not isinstance(value, Hours):
                raise TypeError(f"{field_name} must be an Hours instance")


@dataclass(frozen=True, slots=True)
class LeaveCalculationResult:
    """All calculation periods and their derived totals."""

    leave_year: DateRange
    active_period: DateRange | None
    periods: tuple[LeaveCalculationPeriod, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.leave_year, DateRange):
            raise TypeError("leave_year must be a DateRange")

        if self.active_period is not None and not isinstance(self.active_period, DateRange):
            raise TypeError("active_period must be a DateRange")

        if not isinstance(self.periods, tuple):
            raise TypeError("periods must be a tuple")

        if any(not isinstance(period, LeaveCalculationPeriod) for period in self.periods):
            raise TypeError("periods must contain LeaveCalculationPeriod instances")

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
            value = getattr(period, field_name)

            if not isinstance(value, Hours):
                raise TypeError(f"{field_name} must contain Hours values")

            total += value

        return total
