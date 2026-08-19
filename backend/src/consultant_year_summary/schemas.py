"""API contracts for the consultant-year workbook replacement summary."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel

from annual_entitlement.schemas import EntitlementWorkspace
from carry_forward.schemas import CarryForwardRead
from consultants.schemas import ConsultantRead
from job_plans.schemas import ExactDecimal, JobPlanRead
from leave_bookings.schemas import ActivityHoursRead, LeaveWarningRead, PlanningRead
from leave_years.schemas import LeaveYearRead


class JobPlanPeriodSummary(BaseModel):
    job_plan_id: int
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


class BalancePositionRead(BaseModel):
    available: ActivityHoursRead
    used: ActivityHoursRead
    remaining: ActivityHoursRead


class BalanceViewsRead(BaseModel):
    projected: BalancePositionRead | None
    confirmed: BalancePositionRead | None
    actual: BalancePositionRead | None


class WeekdayCountsRead(BaseModel):
    monday: int
    tuesday: int
    wednesday: int
    thursday: int
    friday: int


class AuditEventRead(BaseModel):
    id: int
    actor_label: str
    entity_type: str
    action: str
    recorded_at: datetime
    details: dict[str, Any]


class LeaveLogEntryRead(BaseModel):
    key: str
    start_date: date
    end_date: date
    description: str
    state: str
    amounts: ActivityHoursRead


class ConsultantYearSummaryRead(BaseModel):
    consultant: ConsultantRead
    leave_year: LeaveYearRead
    job_plans: tuple[JobPlanRead, ...]
    entitlement: EntitlementWorkspace
    carry_forward: CarryForwardRead
    allocation_source: Literal["recommendation", "applied"] | None
    job_plan_periods: tuple[JobPlanPeriodSummary, ...]
    planning: PlanningRead
    leave_log: tuple[LeaveLogEntryRead, ...]
    balances: BalanceViewsRead
    weekday_counts: WeekdayCountsRead
    warnings: tuple[LeaveWarningRead, ...]
    audit_events: tuple[AuditEventRead, ...]
