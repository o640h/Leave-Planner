"""API contracts for holiday settings and consultant-year treatments."""

from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from job_plans.schemas import ExactDecimal

from .models import HolidayCorrectionAction, HolidayTreatmentBasis


class HolidayRead(BaseModel):
    holiday_date: date
    name: str
    notes: str


class HolidayCorrectionWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    holiday_date: date
    action: HolidayCorrectionAction
    replacement_name: str | None = Field(default=None, max_length=160)
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_action(self) -> Self:
        if self.action is HolidayCorrectionAction.ADD_OR_REPLACE and not self.replacement_name:
            raise ValueError("Enter the holiday name being added or replaced")
        if self.action is HolidayCorrectionAction.REMOVE:
            self.replacement_name = None
        return self


class HolidayCorrectionRead(HolidayCorrectionWrite):
    id: int
    created_at: datetime


class HolidaySettingsRead(BaseModel):
    source: str
    source_date: date
    holidays: tuple[HolidayRead, ...]
    corrections: tuple[HolidayCorrectionRead, ...]


class HolidayTreatmentWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    basis: HolidayTreatmentBasis
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def normalise_treatment_details(self) -> Self:
        retained = self.basis is not HolidayTreatmentBasis.STANDARD
        if self.note == "":
            self.note = None
        if not retained:
            self.note = None
        return self


class HolidayOccurrenceRead(BaseModel):
    holiday_date: date
    name: str
    notes: str
    basis: HolidayTreatmentBasis
    treatment_note: str | None
    contracted_pas: ExactDecimal
    deduction_factor: ExactDecimal
    entitlement_hours: ExactDecimal
    dcc_entitlement_hours: ExactDecimal
    spa_entitlement_hours: ExactDecimal
    dcc_deduction_hours: ExactDecimal
    spa_deduction_hours: ExactDecimal


class LeaveYearHolidaysRead(BaseModel):
    source: str
    source_date: date
    entitlement_hours: ExactDecimal
    deduction_hours: ExactDecimal
    occurrences: tuple[HolidayOccurrenceRead, ...]
