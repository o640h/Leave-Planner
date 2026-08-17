"""Consultant public-holiday entitlement and deduction calculation."""

from __future__ import annotations

from decimal import Decimal

from domain import (
    ZERO_HOURS,
    ActivityType,
    CalculationResult,
    CalculationStep,
    Hours,
    ProgrammedActivities,
    RuleId,
)
from job_plans import allocate_hours_by_pa, leave_deduction_factor

from .calendar import holidays_in_period, resolved_holidays
from .models import (
    HolidayTreatmentBasis,
    PublicHolidayOccurrence,
    PublicHolidayRequest,
    PublicHolidayResult,
    PublicHolidayTreatment,
)

PUBLIC_HOLIDAY_FULL_TIME_HOURS = Hours.from_value("8")
PUBLIC_HOLIDAY_PA_CAP = Decimal("10")


def calculate_public_holidays(
    request: PublicHolidayRequest,
) -> CalculationResult[PublicHolidayResult]:
    """Calculate all applicable public holidays in a leave year."""

    active_period = request.active_period
    if active_period is None:
        return CalculationResult(value=PublicHolidayResult(occurrences=()))

    calendar_dates = {holiday.holiday_date for holiday in resolved_holidays(request.calendar)}
    unknown_treatment_dates = {
        treatment.holiday_date
        for treatment in request.treatments
        if treatment.holiday_date not in calendar_dates
    }

    if unknown_treatment_dates:
        formatted_dates = ", ".join(
            holiday_date.isoformat() for holiday_date in sorted(unknown_treatment_dates)
        )
        raise ValueError(
            f"Treatments reference dates that are not public holidays: {formatted_dates}"
        )

    treatments_by_date = {treatment.holiday_date: treatment for treatment in request.treatments}

    occurrences: list[PublicHolidayOccurrence] = []

    for holiday in holidays_in_period(
        request.calendar,
        active_period,
    ):
        job_plan = request.job_plans.version_on(holiday.holiday_date)
        contracted_pas = job_plan.cycle.contracted_pas
        capped_pas = ProgrammedActivities(
            min(
                contracted_pas.value,
                PUBLIC_HOLIDAY_PA_CAP,
            )
        )
        pa_factor = capped_pas.value / PUBLIC_HOLIDAY_PA_CAP
        deduction_factor = leave_deduction_factor(job_plan.cycle)
        entitlement_hours = PUBLIC_HOLIDAY_FULL_TIME_HOURS.scale(pa_factor)
        dcc_entitlement, spa_entitlement, other_entitlement = allocate_hours_by_pa(
            entitlement_hours,
            job_plan.cycle,
        )

        treatment = treatments_by_date.get(
            holiday.holiday_date,
            PublicHolidayTreatment(
                holiday_date=holiday.holiday_date,
                basis=HolidayTreatmentBasis.STANDARD,
            ),
        )

        if treatment.retains_leave:
            dcc_deduction = ZERO_HOURS
            spa_deduction = ZERO_HOURS
            other_deduction = ZERO_HOURS
        else:
            planned_day = job_plan.day_on(holiday.holiday_date)
            dcc_deduction = planned_day.hours_for(ActivityType.DCC).scale(deduction_factor)
            spa_deduction = planned_day.hours_for(ActivityType.SPA).scale(deduction_factor)
            other_deduction = planned_day.hours_for(ActivityType.OTHER).scale(deduction_factor)

        occurrences.append(
            PublicHolidayOccurrence(
                holiday=holiday,
                job_plan_version=job_plan.version_id,
                contracted_pas=contracted_pas,
                capped_pas=capped_pas,
                pa_factor=pa_factor,
                deduction_factor=deduction_factor,
                entitlement_hours=entitlement_hours,
                dcc_entitlement_hours=dcc_entitlement,
                spa_entitlement_hours=spa_entitlement,
                other_entitlement_hours=other_entitlement,
                treatment=treatment,
                dcc_deduction_hours=dcc_deduction,
                spa_deduction_hours=spa_deduction,
                other_deduction_hours=other_deduction,
            )
        )

    result = PublicHolidayResult(occurrences=tuple(occurrences))

    trace = tuple(
        CalculationStep(
            rule_id=RuleId("public-holiday.standard-eight-hours"),
            description=("Calculated public-holiday entitlement and standard job-plan deduction"),
            amount=occurrence.entitlement_hours,
            effective_date=(occurrence.holiday.holiday_date),
            context={
                "holiday_name": occurrence.holiday.name,
                "contracted_pas": str(occurrence.contracted_pas),
                "capped_pas": str(occurrence.capped_pas),
                "pa_factor": format(
                    occurrence.pa_factor,
                    "f",
                ),
                "deduction_factor": format(
                    occurrence.deduction_factor,
                    "f",
                ),
                "dcc_deduction_hours": str(occurrence.dcc_deduction_hours),
                "spa_deduction_hours": str(occurrence.spa_deduction_hours),
                "other_deduction_hours": str(occurrence.other_deduction_hours),
                "treatment": (occurrence.treatment.basis.value),
                "retains_leave": str(occurrence.treatment.retains_leave).lower(),
                "dcc_entitlement_hours": str(occurrence.dcc_entitlement_hours),
                "spa_entitlement_hours": str(occurrence.spa_entitlement_hours),
                "other_entitlement_hours": str(occurrence.other_entitlement_hours),
                "deduction_hours": str(occurrence.deduction_hours),
            },
        )
        for occurrence in result.occurrences
    )

    return CalculationResult(
        value=result,
        trace=trace,
    )
