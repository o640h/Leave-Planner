"""Privacy-shaped API contracts for the read-only Member workspace."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from annual_entitlement.models import EntitlementMode
from annual_entitlement.schemas import (
    EntitlementAmounts,
    EntitlementComponentSummary,
    EntitlementInputs,
)
from job_plans.schemas import ExactDecimal
from leave_bookings.schemas import ActivityHoursRead, LeaveWarningRead

MemberWallchartState = Literal["requested", "approved"]


class MemberConsultantRead(BaseModel):
    name: str
    post_title: str | None


class MemberLeaveYearRead(BaseModel):
    id: int
    start_date: date
    end_date: date
    employment_start: date | None
    employment_end: date | None


class MemberJobPlanDayRead(BaseModel):
    cycle_week: int
    weekday: int
    dcc_hours: ExactDecimal
    spa_hours: ExactDecimal
    other_hours: ExactDecimal


class MemberJobPlanRead(BaseModel):
    effective_from: date
    effective_until: date
    cycle_anchor_date: date | None
    week_count: int
    contracted_pas: ExactDecimal
    dcc_pas: ExactDecimal
    spa_pas: ExactDecimal
    other_pas: ExactDecimal
    hours_per_pa: ExactDecimal
    days: tuple[MemberJobPlanDayRead, ...]


class MemberEntitlementTraceRead(BaseModel):
    description: str
    amount: ExactDecimal | None
    effective_date: date | None


class MemberEntitlementRecommendationRead(BaseModel):
    inputs: EntitlementInputs
    base_entitlement: EntitlementAmounts
    public_holiday_entitlement: EntitlementAmounts
    recommended_entitlement: EntitlementAmounts
    components: tuple[EntitlementComponentSummary, ...]
    trace: tuple[MemberEntitlementTraceRead, ...]


class MemberAppliedEntitlementRead(BaseModel):
    mode: EntitlementMode
    entitlement: EntitlementAmounts
    reason: str | None
    updated_at: datetime


class MemberEntitlementRead(BaseModel):
    recommendation: MemberEntitlementRecommendationRead | None
    application: MemberAppliedEntitlementRead | None


class MemberCarryForwardRead(BaseModel):
    dcc_hours: ExactDecimal
    spa_hours: ExactDecimal
    total_hours: ExactDecimal


class MemberLeaveDayRead(BaseModel):
    leave_date: date
    deduction: ActivityHoursRead
    override_reason: str | None
    public_holiday_name: str | None


class MemberBookingRead(BaseModel):
    start_date: date
    end_date: date
    state: str
    note: str | None
    days: tuple[MemberLeaveDayRead, ...]


class MemberHolidayRead(BaseModel):
    holiday_date: date
    name: str
    basis: str
    entitlement_hours: ExactDecimal
    dcc_deduction_hours: ExactDecimal
    spa_deduction_hours: ExactDecimal


class MemberBalancePositionRead(BaseModel):
    available: ActivityHoursRead
    used: ActivityHoursRead
    remaining: ActivityHoursRead


class MemberBalanceViewsRead(BaseModel):
    requested: MemberBalancePositionRead | None
    approved: MemberBalancePositionRead | None


class MemberJobPlanPeriodRead(BaseModel):
    effective_from: date
    effective_until: date
    calendar_days: int
    contracted_pas: ExactDecimal
    dcc_pas: ExactDecimal
    spa_pas: ExactDecimal
    standard_dcc_hours: ExactDecimal
    standard_spa_hours: ExactDecimal
    gross_entitlement_hours: ExactDecimal
    dcc_entitlement_hours: ExactDecimal
    spa_entitlement_hours: ExactDecimal


class MemberWeekdayCountsRead(BaseModel):
    monday: int
    tuesday: int
    wednesday: int
    thursday: int
    friday: int


class MemberYearSummaryRead(BaseModel):
    leave_year: MemberLeaveYearRead
    job_plans: tuple[MemberJobPlanRead, ...]
    entitlement: MemberEntitlementRead
    carry_forward: MemberCarryForwardRead
    allocation_source: Literal["recommendation", "applied"] | None
    job_plan_periods: tuple[MemberJobPlanPeriodRead, ...]
    holidays: tuple[MemberHolidayRead, ...]
    bookings: tuple[MemberBookingRead, ...]
    balances: MemberBalanceViewsRead
    weekday_counts: MemberWeekdayCountsRead
    warnings: tuple[LeaveWarningRead, ...]


class MemberWorkspaceRead(BaseModel):
    state: Literal["linked", "waiting"]
    workspace_name: str
    consultant: MemberConsultantRead | None = None
    leave_years: tuple[MemberLeaveYearRead, ...] = ()
    selected_year: MemberYearSummaryRead | None = None


class MemberWallchartHolidayRead(BaseModel):
    holiday_date: date
    name: str


class MemberWallchartDateRead(BaseModel):
    leave_date: date
    state: MemberWallchartState


class MemberWallchartPersonRead(BaseModel):
    display_name: str
    leave_dates: tuple[MemberWallchartDateRead, ...]


class MemberWallchartRead(BaseModel):
    month: date
    holidays: tuple[MemberWallchartHolidayRead, ...]
    people: tuple[MemberWallchartPersonRead, ...]
