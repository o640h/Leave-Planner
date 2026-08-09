"""API contracts for annual-entitlement recommendations and applications."""

from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from job_plans.schemas import ExactDecimal, NonNegativeDecimal

from .models import EntitlementMode


class EntitlementAmounts(BaseModel):
    """Exact DCC, SPA, Other, and total hours."""

    dcc_hours: ExactDecimal
    spa_hours: ExactDecimal
    other_hours: ExactDecimal
    total_hours: ExactDecimal


class EntitlementInputs(BaseModel):
    """Inputs responsible for a calculated recommendation."""

    consultant_appointment_date: date
    consultant_service_start_date: date
    policy_versions: tuple[str, ...]
    public_holiday_source: str
    public_holiday_source_date: date


class EntitlementTraceStep(BaseModel):
    """One operator-readable calculation step."""

    rule_id: str
    description: str
    amount: ExactDecimal | None = None
    effective_date: date | None = None
    context: dict[str, str] = Field(default_factory=dict)


class EntitlementRecommendation(BaseModel):
    """A complete unsaved calculation recommendation."""

    inputs: EntitlementInputs
    base_entitlement: EntitlementAmounts
    public_holiday_entitlement: EntitlementAmounts
    recommended_entitlement: EntitlementAmounts
    trace: tuple[EntitlementTraceStep, ...]


class EntitlementRecommendationRead(EntitlementRecommendation):
    """A stored immutable recommendation."""

    id: int
    created_at: datetime


class EntitlementApply(BaseModel):
    """Operator choice applied to the leave ledger."""

    model_config = ConfigDict(str_strip_whitespace=True)

    mode: EntitlementMode

    consultant_appointment_date: date | None = None
    consultant_service_start_date: date | None = None

    dcc_hours: NonNegativeDecimal | None = None
    spa_hours: NonNegativeDecimal | None = None
    other_hours: NonNegativeDecimal = Decimal("0")

    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_mode_inputs(self) -> Self:
        calculated_mode = self.mode in {
            EntitlementMode.CALCULATED,
            EntitlementMode.CALCULATED_WITH_OVERRIDE,
        }

        if calculated_mode and (
            self.consultant_appointment_date is None or self.consultant_service_start_date is None
        ):
            raise ValueError(
                "Appointment and reckonable service dates are required "
                "for a calculated recommendation"
            )

        if self.mode in {
            EntitlementMode.CALCULATED_WITH_OVERRIDE,
            EntitlementMode.MANUAL,
        }:
            if self.dcc_hours is None or self.spa_hours is None:
                raise ValueError("DCC and SPA hours are required for a manual value")

            if not self.reason:
                raise ValueError(
                    "Explain why the applied entitlement differs from the calculated value"
                )

        return self


class AppliedEntitlementRead(BaseModel):
    """The opening values currently applied to the leave ledger."""

    id: int
    leave_year_id: int
    recommendation_id: int | None
    mode: EntitlementMode
    entitlement: EntitlementAmounts
    reason: str | None
    updated_at: datetime


class EntitlementWorkspace(BaseModel):
    """Recommendation and applied values shown together in the interface."""

    recommendation: EntitlementRecommendationRead | None
    application: AppliedEntitlementRead | None
