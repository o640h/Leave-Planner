"""API contracts for leave preview, bookings, and planning."""

from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from domain import LeaveState
from job_plans.schemas import ExactDecimal
from public_holidays.schemas import HolidayOccurrenceRead


class DailyOverrideWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    leave_date: date
    dcc_hours: ExactDecimal | None = Field(default=None, ge=Decimal("0"))
    spa_hours: ExactDecimal | None = Field(default=None, ge=Decimal("0"))
    other_hours: ExactDecimal | None = Field(default=None, ge=Decimal("0"))
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def require_replacement(self) -> Self:
        if self.dcc_hours is self.spa_hours is self.other_hours is None:
            raise ValueError("Replace at least one daily value")
        return self


class LeaveBookingWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    start_date: date
    end_date: date
    state: LeaveState
    note: str | None = Field(default=None, max_length=500)
    overrides: tuple[DailyOverrideWrite, ...] = ()

    @model_validator(mode="after")
    def validate_period(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("End Date cannot be before Start Date")
        if self.note == "":
            self.note = None
        return self


class ActivityHoursRead(BaseModel):
    dcc_hours: ExactDecimal
    spa_hours: ExactDecimal
    other_hours: ExactDecimal
    total_hours: ExactDecimal


class LeaveDayRead(BaseModel):
    leave_date: date
    job_plan_id: int | None
    standard: ActivityHoursRead
    deduction: ActivityHoursRead
    override_reason: str | None
    public_holiday_name: str | None = None


class BalanceRead(BaseModel):
    opening: ActivityHoursRead
    carry_forward: ActivityHoursRead
    public_holidays: ActivityHoursRead
    bookings: ActivityHoursRead
    remaining: ActivityHoursRead


class LeaveWarningRead(BaseModel):
    code: str
    message: str
    severity: str


class LeavePreviewRead(BaseModel):
    days: tuple[LeaveDayRead, ...]
    projected: BalanceRead | None
    confirmed: BalanceRead | None
    actual: BalanceRead | None
    warnings: tuple[LeaveWarningRead, ...]


class LeaveBookingRead(BaseModel):
    id: int
    leave_year_id: int
    start_date: date
    end_date: date
    state: LeaveState
    note: str | None
    days: tuple[LeaveDayRead, ...]
    created_at: datetime
    updated_at: datetime


class PlanningRead(BaseModel):
    leave_year_id: int
    start_date: date
    end_date: date
    holidays: tuple[HolidayOccurrenceRead, ...]
    bookings: tuple[LeaveBookingRead, ...]
    projected: BalanceRead | None
    confirmed: BalanceRead | None
    actual: BalanceRead | None
    warnings: tuple[LeaveWarningRead, ...]
