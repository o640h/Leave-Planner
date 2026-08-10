"""Calendar-day annual leave calculations."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from domain import (
    CalculationResult,
    CalculationStep,
    DateRange,
    Hours,
    RuleId,
)
from job_plans import allocate_hours_by_pa

from .models import (
    LeaveCalculationComponent,
    LeaveCalculationPeriod,
    LeaveCalculationRequest,
    LeaveCalculationResult,
)


def service_anniversary(service_start: date, completed_years: int) -> date:
    """Return a service anniversary, including leap-day starts."""

    if completed_years < 0:
        raise ValueError("Completed years cannot be negative")

    anniversary_year = service_start.year + completed_years
    last_day = monthrange(anniversary_year, service_start.month)[1]

    return date(anniversary_year, service_start.month, min(service_start.day, last_day))


def completed_service_years(service_start: date, calculation_date: date) -> int:
    """Return completed years of service on a date."""

    if calculation_date < service_start:
        raise ValueError("Calculation date cannot precede service start")

    possible_years = calculation_date.year - service_start.year

    if service_anniversary(service_start, possible_years) > calculation_date:
        possible_years -= 1

    return possible_years


def calculate_partial_year_hours(
    annual_hours: Hours,
    *,
    included_days: int,
    leave_year_days: int,
) -> Hours:
    """Calculate the share of annual hours for included calendar days."""

    if leave_year_days < 1:
        raise ValueError("leave_year_days must be greater than zero")

    if not 0 <= included_days <= leave_year_days:
        raise ValueError("included_days must be between zero and leave_year_days")

    fraction = Decimal(included_days) / Decimal(leave_year_days)
    return annual_hours.scale(fraction)


def _service_milestone_dates(request: LeaveCalculationRequest) -> set[date]:
    """Find policy service milestones relevant to this consultant."""

    milestones: set[int] = set()

    for policy in request.policies.versions:
        for era in policy.appointment_eras:
            if era.includes(request.consultant_appointment_date):
                milestones.update(era.service_milestones)

    return {
        service_anniversary(request.consultant_service_start_date, completed_years)
        for completed_years in milestones
    }


def _effective_change_dates(
    request: LeaveCalculationRequest,
    active_period: DateRange,
) -> tuple[date, ...]:
    """Return dates on which a fresh calculation period must begin."""

    change_dates = {active_period.start}

    for policy in request.policies.versions:
        if active_period.start < policy.effective_from <= active_period.end:
            change_dates.add(policy.effective_from)

        if (
            policy.effective_to is not None
            and active_period.start <= policy.effective_to < active_period.end
        ):
            change_dates.add(policy.effective_to + timedelta(days=1))

    for job_plan in request.job_plans.versions:
        if active_period.start < job_plan.effective_from <= active_period.end:
            change_dates.add(job_plan.effective_from)

        if (
            job_plan.effective_to is not None
            and active_period.start <= job_plan.effective_to < active_period.end
        ):
            change_dates.add(job_plan.effective_to + timedelta(days=1))

    for milestone_date in _service_milestone_dates(request):
        if active_period.start < milestone_date <= active_period.end:
            change_dates.add(milestone_date)

    return tuple(sorted(change_dates))


def _calculation_periods(
    request: LeaveCalculationRequest,
    active_period: DateRange,
) -> tuple[DateRange, ...]:
    """Split active employment into periods with constant inputs."""

    starts = _effective_change_dates(request, active_period)
    periods: list[DateRange] = []

    for index, start in enumerate(starts):
        if index + 1 < len(starts):
            end = starts[index + 1] - timedelta(days=1)
        else:
            end = active_period.end

        periods.append(DateRange(start, end))

    return tuple(periods)


def _calculate_period(
    request: LeaveCalculationRequest,
    period: DateRange,
) -> CalculationResult[LeaveCalculationPeriod]:
    """Calculate one period with constant policy and job-plan inputs."""

    policy = request.policies.version_on(period.start)
    job_plan = request.job_plans.version_on(period.start)
    service_years = completed_service_years(
        request.consultant_service_start_date,
        period.start,
    )

    resolved = policy.resolve(
        calculation_date=period.start,
        consultant_appointment_date=request.consultant_appointment_date,
        completed_service_years=service_years,
        contracted_pas=job_plan.cycle.contracted_pas,
    )
    entitlement = resolved.value

    year_fraction = Decimal(period.calendar_days) / Decimal(request.leave_year.calendar_days)
    period_entitlement = calculate_partial_year_hours(
        entitlement.annual_hours,
        included_days=period.calendar_days,
        leave_year_days=request.leave_year.calendar_days,
    )
    dcc, spa, other = allocate_hours_by_pa(period_entitlement, job_plan.cycle)
    components = tuple(
        LeaveCalculationComponent(
            rule_id=amount.component.rule_id,
            label=amount.component.label,
            kind=amount.component.kind,
            full_time_hours=amount.component.full_time_hours,
            annual_adjusted_hours=amount.adjusted_hours,
            period_hours=calculate_partial_year_hours(
                amount.adjusted_hours,
                included_days=period.calendar_days,
                leave_year_days=request.leave_year.calendar_days,
            ),
        )
        for amount in entitlement.components
    )

    calculated_period = LeaveCalculationPeriod(
        period=period,
        completed_service_years=service_years,
        policy_version=policy.version,
        job_plan_version=job_plan.version_id,
        year_fraction=year_fraction,
        full_year_hours=entitlement.annual_hours,
        entitlement_hours=period_entitlement,
        dcc_hours=dcc,
        spa_hours=spa,
        other_hours=other,
        components=components,
    )

    period_step = CalculationStep(
        rule_id=RuleId("leave-calculation.calendar-days"),
        description="Calculated annual entitlement for a constant-input calendar period",
        amount=calculated_period.entitlement_hours,
        effective_date=calculated_period.period.start,
        context={
            "period_start": calculated_period.period.start.isoformat(),
            "period_end": calculated_period.period.end.isoformat(),
            "calendar_days": str(calculated_period.period.calendar_days),
            "leave_year_days": str(request.leave_year.calendar_days),
            "year_fraction": format(calculated_period.year_fraction, "f"),
            "full_year_hours": str(calculated_period.full_year_hours),
            "policy_version": calculated_period.policy_version,
            "job_plan_version": str(calculated_period.job_plan_version),
            "completed_service_years": str(calculated_period.completed_service_years),
            "dcc_hours": str(calculated_period.dcc_hours),
            "spa_hours": str(calculated_period.spa_hours),
            "other_hours": str(calculated_period.other_hours),
        },
    )
    return CalculationResult(value=calculated_period, trace=(*resolved.trace, period_step))


def calculate_leave_entitlement(
    request: LeaveCalculationRequest,
) -> CalculationResult[LeaveCalculationResult]:
    """Calculate annual entitlement across all effective changes."""

    active_period = request.active_period

    if active_period is None:
        return CalculationResult(
            value=LeaveCalculationResult(
                leave_year=request.leave_year,
                active_period=None,
                periods=(),
            )
        )

    period_calculations = tuple(
        _calculate_period(request, period)
        for period in _calculation_periods(request, active_period)
    )
    periods = tuple(calculation.value for calculation in period_calculations)
    result = LeaveCalculationResult(
        leave_year=request.leave_year,
        active_period=active_period,
        periods=periods,
    )

    trace = tuple(step for calculation in period_calculations for step in calculation.trace)

    return CalculationResult(value=result, trace=trace)
