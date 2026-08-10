"""Calculation and persistence orchestration for annual entitlement."""

import json
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from audit import record_audit_event
from domain import CalculationStep, DateRange
from entitlement_policy import DEFAULT_ENTITLEMENT_POLICIES
from errors import ApiError
from job_plans import JobPlanHistory
from job_plans import service as job_plan_service
from leave_calculation import (
    LeaveCalculationRequest,
    calculate_leave_entitlement,
)
from leave_years import service as leave_year_service
from leave_years.models import LeaveYear
from public_holidays import (
    PublicHolidayRequest,
    calculate_public_holidays,
)
from public_holidays import service as public_holiday_service

from .models import EntitlementMode
from .persistence import (
    AppliedEntitlementRecord,
    EntitlementRecommendationRecord,
)
from .schemas import (
    AppliedEntitlementRead,
    EntitlementAmounts,
    EntitlementApply,
    EntitlementComponentSummary,
    EntitlementInputs,
    EntitlementRecommendation,
    EntitlementRecommendationRead,
    EntitlementTraceStep,
    EntitlementWorkspace,
)


def amounts(
    dcc_hours: Decimal,
    spa_hours: Decimal,
    other_hours: Decimal,
) -> EntitlementAmounts:
    """Build an activity split and its derived total."""

    return EntitlementAmounts(
        dcc_hours=dcc_hours,
        spa_hours=spa_hours,
        other_hours=other_hours,
        total_hours=dcc_hours + spa_hours + other_hours,
    )


def trace_step(step: CalculationStep) -> EntitlementTraceStep:
    """Convert a pure calculation step into an API result."""

    return EntitlementTraceStep(
        rule_id=str(step.rule_id),
        description=step.description,
        amount=step.amount.value if step.amount is not None else None,
        effective_date=step.effective_date,
        context=dict(step.context),
    )


def active_period(leave_year: LeaveYear) -> DateRange | None:
    """Return employment clipped to the selected leave year."""

    start = max(
        leave_year.start_date,
        leave_year.employment_start or leave_year.start_date,
    )
    end = min(
        leave_year.end_date,
        leave_year.employment_end or leave_year.end_date,
    )

    if end < start:
        return None

    return DateRange(start, end)


def ensure_job_plan_coverage(
    period: DateRange | None,
    history: JobPlanHistory,
) -> None:
    """Prevent calculations across dates without an effective job plan."""

    if period is None:
        return

    try:
        for calculation_date in period.dates():
            history.version_on(calculation_date)
    except LookupError as error:
        raise ApiError(
            status_code=422,
            code="job_plan_gap",
            message=(
                "A job plan must cover every active date in the leave year "
                "before entitlement can be calculated."
            ),
        ) from error


def calculation_history(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
) -> JobPlanHistory:
    """Load the selected leave year's effective job plans."""

    records = job_plan_service.list_job_plans(
        session,
        consultant_id,
        leave_year_id,
    )

    if not records:
        raise ApiError(
            status_code=422,
            code="job_plan_required",
            message=("Add a job plan before calculating annual entitlement."),
        )

    return job_plan_service.calculation_history(records)


def calculate_recommendation(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    *,
    consultant_appointment_date: date,
    consultant_service_start_date: date,
) -> EntitlementRecommendation:
    """Calculate base leave and public-holiday entitlement."""

    leave_year = leave_year_service.get_leave_year(
        session,
        consultant_id,
        leave_year_id,
    )
    period = active_period(leave_year)

    if period is not None:
        if consultant_appointment_date > period.start:
            raise ApiError(
                status_code=422,
                code="appointment_date_after_leave_year",
                message=(
                    "The consultant appointment date cannot be after their active leave-year start."
                ),
            )

        if consultant_service_start_date > period.start:
            raise ApiError(
                status_code=422,
                code="service_date_after_leave_year",
                message=(
                    "The reckonable service date cannot be after their active leave-year start."
                ),
            )

    history = calculation_history(
        session,
        consultant_id,
        leave_year_id,
    )
    ensure_job_plan_coverage(period, history)

    period_dates = DateRange(
        leave_year.start_date,
        leave_year.end_date,
    )
    employment_start = leave_year.employment_start or leave_year.start_date

    base_calculation = calculate_leave_entitlement(
        LeaveCalculationRequest(
            leave_year=period_dates,
            employment_start=employment_start,
            employment_end=leave_year.employment_end,
            consultant_appointment_date=(consultant_appointment_date),
            consultant_service_start_date=(consultant_service_start_date),
            policies=DEFAULT_ENTITLEMENT_POLICIES,
            job_plans=history,
        )
    )

    holiday_calendar = public_holiday_service.active_calendar(session)
    holiday_calculation = calculate_public_holidays(
        PublicHolidayRequest(
            leave_year=period_dates,
            employment_start=employment_start,
            employment_end=leave_year.employment_end,
            calendar=holiday_calendar,
            job_plans=history,
            treatments=public_holiday_service.treatments_for_leave_year(session, leave_year_id),
        )
    )

    base = base_calculation.value
    holidays = holiday_calculation.value

    base_amounts = amounts(
        base.dcc_hours.value,
        base.spa_hours.value,
        base.other_hours.value,
    )
    holiday_amounts = amounts(
        holidays.dcc_entitlement_hours.value,
        holidays.spa_entitlement_hours.value,
        holidays.other_entitlement_hours.value,
    )
    recommended_amounts = amounts(
        base_amounts.dcc_hours + holiday_amounts.dcc_hours,
        base_amounts.spa_hours + holiday_amounts.spa_hours,
        base_amounts.other_hours + holiday_amounts.other_hours,
    )

    policy_versions = tuple(
        dict.fromkeys(calculation_period.policy_version for calculation_period in base.periods)
    )
    component_totals: dict[tuple[str, str], dict[str, Decimal]] = {}
    for calculation_period in base.periods:
        for component in calculation_period.components:
            key = (component.label, component.kind.value)
            current = component_totals.setdefault(
                key,
                {
                    "full_time_hours": component.full_time_hours.value,
                    "prorated_hours": Decimal("0"),
                },
            )
            current["prorated_hours"] += component.period_hours.value

    components = tuple(
        EntitlementComponentSummary(
            label=label,
            kind=kind,
            full_time_hours=values["full_time_hours"],
            prorated_hours=values["prorated_hours"],
        )
        for (label, kind), values in component_totals.items()
    )

    return EntitlementRecommendation(
        inputs=EntitlementInputs(
            consultant_appointment_date=(consultant_appointment_date),
            consultant_service_start_date=(consultant_service_start_date),
            policy_versions=policy_versions,
            public_holiday_source=holiday_calendar.source.value,
            public_holiday_source_date=holiday_calendar.source_date,
        ),
        base_entitlement=base_amounts,
        public_holiday_entitlement=holiday_amounts,
        recommended_entitlement=recommended_amounts,
        components=components,
        trace=tuple(
            trace_step(step) for step in (base_calculation.trace + holiday_calculation.trace)
        ),
    )


def store_recommendation(
    session: Session,
    leave_year_id: int,
    recommendation: EntitlementRecommendation,
) -> EntitlementRecommendationRecord:
    """Append an immutable recommendation snapshot."""

    record = EntitlementRecommendationRecord(
        leave_year_id=leave_year_id,
        inputs_json=recommendation.inputs.model_dump_json(),
        result_json=json.dumps(
            {
                "base_entitlement": (recommendation.base_entitlement.model_dump(mode="json")),
                "public_holiday_entitlement": (
                    recommendation.public_holiday_entitlement.model_dump(mode="json")
                ),
                "recommended_entitlement": (
                    recommendation.recommended_entitlement.model_dump(mode="json")
                ),
                "components": [
                    component.model_dump(mode="json") for component in recommendation.components
                ],
            },
            sort_keys=True,
        ),
        trace_json=json.dumps(
            [step.model_dump(mode="json") for step in recommendation.trace],
            sort_keys=True,
        ),
    )
    session.add(record)
    session.flush()
    session.refresh(record)
    return record


def recommendation_read(
    record: EntitlementRecommendationRecord,
) -> EntitlementRecommendationRead:
    """Rebuild a stored recommendation for the API."""

    results = json.loads(record.result_json)

    return EntitlementRecommendationRead(
        id=record.id,
        created_at=record.created_at,
        inputs=EntitlementInputs.model_validate_json(record.inputs_json),
        base_entitlement=EntitlementAmounts.model_validate(results["base_entitlement"]),
        public_holiday_entitlement=(
            EntitlementAmounts.model_validate(results["public_holiday_entitlement"])
        ),
        recommended_entitlement=(
            EntitlementAmounts.model_validate(results["recommended_entitlement"])
        ),
        components=tuple(
            EntitlementComponentSummary.model_validate(component)
            for component in results.get("components", [])
        ),
        trace=tuple(
            EntitlementTraceStep.model_validate(step) for step in json.loads(record.trace_json)
        ),
    )


def application_read(
    record: AppliedEntitlementRecord,
) -> AppliedEntitlementRead:
    """Convert the stored applied values into an API response."""

    return AppliedEntitlementRead(
        id=record.id,
        leave_year_id=record.leave_year_id,
        recommendation_id=record.recommendation_id,
        mode=EntitlementMode(record.mode),
        entitlement=amounts(
            record.dcc_hours,
            record.spa_hours,
            record.other_hours,
        ),
        reason=record.reason,
        updated_at=record.updated_at,
    )


def current_application(
    session: Session,
    leave_year_id: int,
) -> AppliedEntitlementRecord | None:
    statement = select(AppliedEntitlementRecord).where(
        AppliedEntitlementRecord.leave_year_id == leave_year_id
    )
    return session.scalar(statement)


def get_workspace(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
) -> EntitlementWorkspace:
    """Return the recommendation and values currently in force."""

    leave_year_service.get_leave_year(
        session,
        consultant_id,
        leave_year_id,
    )
    application = current_application(session, leave_year_id)

    if application is None:
        return EntitlementWorkspace(
            recommendation=None,
            application=None,
        )

    recommendation = None
    if application.recommendation_id is not None:
        stored = session.get(
            EntitlementRecommendationRecord,
            application.recommendation_id,
        )
        if stored is not None:
            recommendation = recommendation_read(stored)

    return EntitlementWorkspace(
        recommendation=recommendation,
        application=application_read(application),
    )


def apply_entitlement(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    details: EntitlementApply,
    *,
    audit_action: str = "applied",
) -> EntitlementWorkspace:
    """Calculate or accept values and apply them to the leave ledger."""

    leave_year_service.get_leave_year(
        session,
        consultant_id,
        leave_year_id,
    )

    recommendation_record = None
    recommendation = None

    if details.mode is not EntitlementMode.MANUAL:
        assert details.consultant_appointment_date is not None
        assert details.consultant_service_start_date is not None

        recommendation = calculate_recommendation(
            session,
            consultant_id,
            leave_year_id,
            consultant_appointment_date=(details.consultant_appointment_date),
            consultant_service_start_date=(details.consultant_service_start_date),
        )
        recommendation_record = store_recommendation(
            session,
            leave_year_id,
            recommendation,
        )

    if details.mode is EntitlementMode.CALCULATED:
        assert recommendation is not None
        applied = recommendation.recommended_entitlement
    else:
        assert details.dcc_hours is not None
        assert details.spa_hours is not None

        applied = amounts(
            details.dcc_hours,
            details.spa_hours,
            details.other_hours,
        )

    application = current_application(session, leave_year_id)
    before = (
        application_read(application).model_dump(mode="json") if application is not None else None
    )

    if application is None:
        application = AppliedEntitlementRecord(
            leave_year_id=leave_year_id,
        )
        session.add(application)

    application.recommendation_id = (
        recommendation_record.id if recommendation_record is not None else None
    )
    application.mode = details.mode.value
    application.dcc_hours = applied.dcc_hours
    application.spa_hours = applied.spa_hours
    application.other_hours = applied.other_hours
    application.reason = details.reason

    session.flush()
    session.refresh(application)

    record_audit_event(
        session,
        consultant_id=consultant_id,
        entity_type="applied_entitlement",
        entity_id=application.id,
        action=audit_action,
        details={
            "before": before,
            "after": application_read(application).model_dump(mode="json"),
        },
    )

    return get_workspace(
        session,
        consultant_id,
        leave_year_id,
    )


def refresh_entitlement(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
) -> EntitlementWorkspace:
    """Refresh a stored recommendation after its source configuration changes."""

    leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    application = current_application(session, leave_year_id)

    if (
        application is None
        or application.mode == EntitlementMode.MANUAL.value
        or application.recommendation_id is None
    ):
        return get_workspace(session, consultant_id, leave_year_id)

    stored = session.get(EntitlementRecommendationRecord, application.recommendation_id)
    if stored is None:
        return get_workspace(session, consultant_id, leave_year_id)

    inputs = recommendation_read(stored).inputs
    mode = EntitlementMode(application.mode)
    details = EntitlementApply(
        mode=mode,
        consultant_appointment_date=inputs.consultant_appointment_date,
        consultant_service_start_date=inputs.consultant_service_start_date,
        dcc_hours=(
            application.dcc_hours if mode is EntitlementMode.CALCULATED_WITH_OVERRIDE else None
        ),
        spa_hours=(
            application.spa_hours if mode is EntitlementMode.CALCULATED_WITH_OVERRIDE else None
        ),
        other_hours=application.other_hours,
        reason=application.reason,
    )

    return apply_entitlement(
        session,
        consultant_id,
        leave_year_id,
        details,
        audit_action="refreshed",
    )
