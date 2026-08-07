"""Daily activity and repeating-cycle job-plan models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import IntEnum

from domain import ZERO_HOURS, ActivityType, Hours, ProgrammedActivities


class Weekday(IntEnum):
    """Weekdays using the same numbering as datetime.date.weekday()."""

    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


@dataclass(frozen=True, slots=True)
class ActivityAllocation:
    """Visible hours allocated to one activity type on one job-plan day."""

    activity_type: ActivityType
    hours: Hours

    def __post_init__(self) -> None:
        if not isinstance(self.activity_type, ActivityType):
            raise TypeError("Activity allocation type must be an ActivityType")
        if not isinstance(self.hours, Hours):
            raise TypeError("Activity allocation hours must be an Hours instance")
        if self.hours.value <= 0:
            raise ValueError("Activity allocation hours must be greater than zero")


@dataclass(frozen=True, slots=True)
class JobPlanDay:
    """The standard DCC, SPA, and Other hours for one cycle day."""

    cycle_week: int
    weekday: Weekday
    activities: tuple[ActivityAllocation, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.cycle_week, bool) or not isinstance(self.cycle_week, int):
            raise TypeError("Cycle week must be an integer")
        if self.cycle_week < 1:
            raise ValueError("Cycle week must be at least one")
        if not isinstance(self.weekday, Weekday):
            raise TypeError("Job-plan weekday must be a Weekday")
        if not isinstance(self.activities, tuple):
            raise TypeError("Job-plan activities must be a tuple")
        if any(not isinstance(activity, ActivityAllocation) for activity in self.activities):
            raise TypeError("Job-plan activities must contain ActivityAllocation instances")

        activity_types = tuple(activity.activity_type for activity in self.activities)
        if len(activity_types) != len(set(activity_types)):
            raise ValueError("A job-plan day cannot repeat an activity type")

    @property
    def total_hours(self) -> Hours:
        """Return all visible activity hours planned for this day."""

        total = ZERO_HOURS
        for activity in self.activities:
            total += activity.hours
        return total

    def hours_for(self, activity_type: ActivityType) -> Hours:
        """Return visible hours for one activity type, or zero if absent."""

        if not isinstance(activity_type, ActivityType):
            raise TypeError("activity_type must be an ActivityType")

        for activity in self.activities:
            if activity.activity_type is activity_type:
                return activity.hours
        return ZERO_HOURS


@dataclass(frozen=True, slots=True)
class JobPlanCycle:
    """A complete one-week or multi-week repeating job-plan cycle.

    Contracted activity PAs determine the DCC/SPA/Other entitlement split.
    Daily activity hours mirror the workbook's standard deduction row and may
    exclude flexibly delivered activity, so they are reported but are not
    required to equal the contracted PA total.
    """

    week_count: int
    contracted_pas: ProgrammedActivities
    dcc_pas: ProgrammedActivities
    spa_pas: ProgrammedActivities
    other_pas: ProgrammedActivities
    hours_per_pa: Hours
    days: tuple[JobPlanDay, ...]
    reconciliation_override_reason: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.week_count, bool) or not isinstance(self.week_count, int):
            raise TypeError("Job-plan week count must be an integer")
        if self.week_count < 1:
            raise ValueError("A job-plan cycle must contain at least one week")
        if not isinstance(self.contracted_pas, ProgrammedActivities):
            raise TypeError("contracted_pas must be ProgrammedActivities")

        for field_name, value in (
            ("dcc_pas", self.dcc_pas),
            ("spa_pas", self.spa_pas),
            ("other_pas", self.other_pas),
        ):
            if not isinstance(value, ProgrammedActivities):
                raise TypeError(f"{field_name} must be ProgrammedActivities")

        if not isinstance(self.hours_per_pa, Hours):
            raise TypeError("hours_per_pa must be an Hours instance")
        if self.hours_per_pa.value <= 0:
            raise ValueError("hours_per_pa must be greater than zero")
        if not isinstance(self.days, tuple):
            raise TypeError("Job-plan days must be a tuple")
        if any(not isinstance(day, JobPlanDay) for day in self.days):
            raise TypeError("Job-plan days must contain JobPlanDay instances")

        self._validate_day_positions()
        self._validate_reconciliation()

    def _validate_day_positions(self) -> None:
        """Require exactly one record for every day in the cycle."""

        actual_positions = tuple((day.cycle_week, day.weekday) for day in self.days)
        if len(actual_positions) != len(set(actual_positions)):
            raise ValueError("A job-plan cycle cannot contain duplicate days")

        expected_positions = {
            (cycle_week, weekday)
            for cycle_week in range(1, self.week_count + 1)
            for weekday in Weekday
        }
        if set(actual_positions) != expected_positions:
            raise ValueError(
                "A job-plan cycle must contain exactly one record "
                "for every weekday in every cycle week"
            )

    def _validate_reconciliation(self) -> None:
        """Require the activity PA split to equal total contracted PAs."""

        reason = self.reconciliation_override_reason
        if reason is not None and (not isinstance(reason, str) or not reason.strip()):
            raise ValueError("Reconciliation override reason cannot be blank")
        if not self.is_reconciled and reason is None:
            raise ValueError(
                "DCC, SPA, and Other PAs do not reconcile with total "
                "contracted PAs; provide a reconciliation override reason"
            )

    @property
    def allocated_pas(self) -> ProgrammedActivities:
        """Return PAs allocated across DCC, SPA, and Other."""

        return ProgrammedActivities(self.dcc_pas.value + self.spa_pas.value + self.other_pas.value)

    @property
    def reconciliation_variance(self) -> Decimal:
        """Return allocated activity PAs minus total contracted PAs."""

        return self.allocated_pas.value - self.contracted_pas.value

    @property
    def is_reconciled(self) -> bool:
        """Return whether activity PAs equal total contracted PAs."""

        return self.reconciliation_variance == Decimal("0")

    def pas_for(self, activity_type: ActivityType) -> ProgrammedActivities:
        """Return contracted PAs for DCC, SPA, or Other."""

        if not isinstance(activity_type, ActivityType):
            raise TypeError("activity_type must be an ActivityType")
        if activity_type is ActivityType.DCC:
            return self.dcc_pas
        if activity_type is ActivityType.SPA:
            return self.spa_pas
        return self.other_pas

    def activity_proportion(self, activity_type: ActivityType) -> Decimal:
        """Return an activity's share of the allocated contracted PAs."""

        if self.allocated_pas.value == 0:
            return Decimal("0")
        return self.pas_for(activity_type).value / self.allocated_pas.value

    @property
    def actual_cycle_hours(self) -> Hours:
        """Return visible standard hours across the complete cycle."""

        total = ZERO_HOURS
        for day in self.days:
            total += day.total_hours
        return total

    @property
    def average_weekly_hours(self) -> Hours:
        """Return average visible standard hours per week."""

        return self.actual_cycle_hours.scale(Decimal("1") / Decimal(self.week_count))

    @property
    def scheduled_average_weekly_pas(self) -> ProgrammedActivities:
        """Convert visible average weekly hours into informational PAs."""

        return ProgrammedActivities(self.average_weekly_hours.value / self.hours_per_pa.value)

    def activity_hours(self, activity_type: ActivityType) -> Hours:
        """Return visible cycle hours for DCC, SPA, or Other."""

        if not isinstance(activity_type, ActivityType):
            raise TypeError("activity_type must be an ActivityType")

        total = ZERO_HOURS
        for day in self.days:
            total += day.hours_for(activity_type)
        return total

    def day(self, cycle_week: int, weekday: Weekday) -> JobPlanDay:
        """Return one explicitly recorded day in the cycle."""

        for job_plan_day in self.days:
            if job_plan_day.cycle_week == cycle_week and job_plan_day.weekday is weekday:
                return job_plan_day
        raise LookupError("Job-plan day was not found in the complete cycle")

    def day_on(self, target_date: date, *, cycle_anchor_date: date) -> JobPlanDay:
        """Map a calendar date onto its repeating cycle position."""

        if type(target_date) is not date:
            raise TypeError("Target date must be a date")
        if type(cycle_anchor_date) is not date:
            raise TypeError("Cycle anchor date must be a date")
        if cycle_anchor_date.weekday() != Weekday.MONDAY:
            raise ValueError("Cycle anchor date must be a Monday")

        days_from_anchor = (target_date - cycle_anchor_date).days
        cycle_week = ((days_from_anchor // 7) % self.week_count) + 1
        weekday = Weekday(target_date.weekday())
        return self.day(cycle_week, weekday)
