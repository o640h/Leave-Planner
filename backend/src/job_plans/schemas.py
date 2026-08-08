"""API contracts for consultant job plans."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
    model_validator,
)


def parse_exact_decimal(value: object) -> Decimal:
    """Accept exact decimal strings and database Decimal values only."""

    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, str):
        try:
            result = Decimal(value.strip())
        except InvalidOperation as error:
            raise ValueError("Enter a valid decimal value") from error
    else:
        raise ValueError("Decimal quantities must be sent as strings")

    if not result.is_finite():
        raise ValueError("Decimal quantities must be finite")

    return result


def serialize_decimal(value: Decimal) -> str:
    return format(value, "f")


ExactDecimal = Annotated[
    Decimal,
    BeforeValidator(parse_exact_decimal),
    PlainSerializer(
        serialize_decimal,
        return_type=str,
        when_used="json",
    ),
]

NonNegativeDecimal = Annotated[ExactDecimal, Field(ge=0)]
PositiveDecimal = Annotated[ExactDecimal, Field(gt=0)]
WeekdayNumber = Annotated[int, Field(ge=0, le=6)]


class JobPlanDayFields(BaseModel):
    """One weekday in a repeating job-plan pattern."""

    model_config = ConfigDict(from_attributes=True)

    cycle_week: int = Field(ge=1)
    weekday: WeekdayNumber
    dcc_hours: NonNegativeDecimal
    spa_hours: NonNegativeDecimal
    other_hours: NonNegativeDecimal


class JobPlanFields(BaseModel):
    """Fields shared by preview, create, edit, and read operations."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )

    effective_from: date
    effective_until: date
    cycle_anchor_date: date | None = None
    week_count: int = Field(ge=1)

    contracted_pas: NonNegativeDecimal
    dcc_pas: NonNegativeDecimal
    spa_pas: NonNegativeDecimal
    other_pas: NonNegativeDecimal
    hours_per_pa: PositiveDecimal = Decimal("4")

    reconciliation_override_reason: str | None = Field(
        default=None,
        max_length=500,
    )
    days: tuple[JobPlanDayFields, ...]

    @field_validator("reconciliation_override_reason", mode="before")
    @classmethod
    def blank_reason_is_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_dates_and_cycle(self) -> Self:
        if self.effective_until <= self.effective_from:
            raise ValueError("Effective Until must be after Effective From")

        if self.cycle_anchor_date is not None:
            if self.cycle_anchor_date.weekday() != 0:
                raise ValueError("The cycle anchor must be a Monday")
            if self.cycle_anchor_date > self.effective_from:
                raise ValueError("The cycle anchor cannot be after Effective From")

        positions = {(day.cycle_week, day.weekday) for day in self.days}
        expected = {
            (cycle_week, weekday)
            for cycle_week in range(1, self.week_count + 1)
            for weekday in range(7)
        }

        if len(positions) != len(self.days):
            raise ValueError("The job-plan pattern contains duplicate days")

        if positions != expected:
            raise ValueError("Provide one record for every weekday in every cycle week")

        return self


class JobPlanWrite(JobPlanFields):
    """Fields that may be committed to the job-plan history."""

    @model_validator(mode="after")
    def require_reconciliation_reason(self) -> Self:
        allocated_pas = self.dcc_pas + self.spa_pas + self.other_pas

        if allocated_pas != self.contracted_pas and self.reconciliation_override_reason is None:
            raise ValueError("Explain why the activity PAs do not equal total contracted PAs")

        return self


class JobPlanCreate(JobPlanWrite):
    """Information accepted when creating a job plan."""


class JobPlanUpdate(JobPlanWrite):
    """Complete replacement accepted when editing a job plan."""


class JobPlanRead(JobPlanFields):
    """A persisted job plan returned to the frontend."""

    id: int
    leave_year_id: int


class JobPlanPreview(JobPlanFields):
    """Calculated information shown before a job plan is saved."""

    allocated_pas: ExactDecimal
    reconciliation_variance: ExactDecimal
    is_reconciled: bool
    average_visible_hours: ExactDecimal
    average_dcc_hours: ExactDecimal
    average_spa_hours: ExactDecimal
    average_other_hours: ExactDecimal
    scheduled_average_pas: ExactDecimal
    warning: str | None
