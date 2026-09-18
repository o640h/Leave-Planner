"""Small builders shared by the executable reference cases."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from annual_entitlement import AppliedEntitlement
from domain import ActivityType, DateRange, Hours, LeaveState, ProgrammedActivities, RuleId
from entitlement_policy import DEFAULT_ENTITLEMENT_POLICIES
from job_plans import (
    ActivityAllocation,
    JobPlanCycle,
    JobPlanDay,
    JobPlanHistory,
    JobPlanVersion,
    Weekday,
)
from leave_calculation import LeaveCalculationRequest, calculate_leave_entitlement
from leave_records import LeaveBooking, LeaveRecordsRequest
from public_holidays import (
    ENGLAND_WALES_SNAPSHOT,
    PublicHolidayRequest,
    PublicHolidayTreatment,
    calculate_public_holidays,
)

DayPattern = Mapping[
    tuple[int, Weekday],
    tuple[tuple[ActivityType, str], ...],
]


def hours(value: str) -> Hours:
    return Hours.from_value(value)


def cycle(
    *,
    week_count: int,
    contracted_pas: str,
    dcc_pas: str,
    spa_pas: str,
    other_pas: str = "0",
    pattern: DayPattern | None = None,
    override_reason: str | None = None,
) -> JobPlanCycle:
    """Build a complete cycle while keeping visible days easy to read."""

    visible_pattern = pattern or {}
    days = tuple(
        JobPlanDay(
            cycle_week,
            weekday,
            tuple(
                ActivityAllocation(activity_type, hours(value))
                for activity_type, value in visible_pattern.get((cycle_week, weekday), ())
            ),
        )
        for cycle_week in range(1, week_count + 1)
        for weekday in Weekday
    )
    return JobPlanCycle(
        week_count=week_count,
        contracted_pas=ProgrammedActivities.from_value(contracted_pas),
        dcc_pas=ProgrammedActivities.from_value(dcc_pas),
        spa_pas=ProgrammedActivities.from_value(spa_pas),
        other_pas=ProgrammedActivities.from_value(other_pas),
        hours_per_pa=hours("4"),
        days=days,
        reconciliation_override_reason=override_reason,
    )


def job_plan(
    *,
    version_id: str,
    effective_from: date,
    effective_to: date | None,
    job_cycle: JobPlanCycle,
) -> JobPlanVersion:
    """Create an effective version anchored to the preceding Monday."""

    anchor = effective_from
    while anchor.weekday() != Weekday.MONDAY:
        anchor = date.fromordinal(anchor.toordinal() - 1)

    return JobPlanVersion(
        version_id=RuleId(version_id),
        effective_from=effective_from,
        effective_to=effective_to,
        cycle_anchor_date=anchor,
        cycle=job_cycle,
    )


def booking(
    booking_id: str,
    start: date,
    end: date | None = None,
    state: LeaveState = LeaveState.APPROVED,
) -> LeaveBooking:
    return LeaveBooking(
        booking_id=booking_id,
        period=DateRange(start, end or start),
        state=state,
    )


def request(
    *,
    leave_year: DateRange,
    employment_start: date,
    consultant_appointment_date: date,
    consultant_service_start_date: date,
    job_plans: JobPlanHistory,
    bookings: tuple[LeaveBooking, ...] = (),
    treatments: tuple[PublicHolidayTreatment, ...] = (),
) -> LeaveRecordsRequest:
    """Run the real entitlement and holiday engines for one fixture."""

    entitlement = calculate_leave_entitlement(
        LeaveCalculationRequest(
            leave_year=leave_year,
            employment_start=employment_start,
            employment_end=None,
            consultant_appointment_date=consultant_appointment_date,
            consultant_service_start_date=consultant_service_start_date,
            policies=DEFAULT_ENTITLEMENT_POLICIES,
            job_plans=job_plans,
        )
    ).value
    public_holidays = calculate_public_holidays(
        PublicHolidayRequest(
            leave_year=leave_year,
            employment_start=employment_start,
            employment_end=None,
            calendar=ENGLAND_WALES_SNAPSHOT,
            job_plans=job_plans,
            treatments=treatments,
        )
    ).value
    return LeaveRecordsRequest(
        leave_year=leave_year,
        # The ledger now receives the operator-applied opening entitlement.
        # For calculation fixtures, that is the unmodified recommendation:
        # base policy entitlement plus public-holiday entitlement.
        entitlement=AppliedEntitlement(
            dcc_hours=(entitlement.dcc_hours + public_holidays.dcc_entitlement_hours),
            spa_hours=(entitlement.spa_hours + public_holidays.spa_entitlement_hours),
            other_hours=(entitlement.other_hours + public_holidays.other_entitlement_hours),
        ),
        public_holidays=public_holidays,
        job_plans=job_plans,
        bookings=bookings,
    )
