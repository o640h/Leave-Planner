"""Privacy-preserving orchestration for the linked Member experience."""

from calendar import monthrange
from datetime import date, timedelta
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from consultant_year_summary.service import get_summary
from consultants.models import Consultant
from errors import ApiError
from leave_bookings import service as leave_booking_service
from leave_bookings.persistence import LeaveBookingRecord
from leave_bookings.schemas import LeavePreviewRead, LeaveRequestWrite
from leave_years import service as leave_year_service
from leave_years.models import LeaveYear
from public_holidays import service as holiday_service
from public_holidays.calendar import resolved_holidays
from workspaces.models import Workspace
from workspaces.service import WorkspaceAccess

from .schemas import (
    MemberAppliedEntitlementRead,
    MemberBalancePositionRead,
    MemberBalanceViewsRead,
    MemberBookingRead,
    MemberCarryForwardRead,
    MemberConsultantRead,
    MemberEntitlementRead,
    MemberEntitlementRecommendationRead,
    MemberEntitlementTraceRead,
    MemberHolidayRead,
    MemberJobPlanDayRead,
    MemberJobPlanPeriodRead,
    MemberJobPlanRead,
    MemberLeaveDayRead,
    MemberLeaveYearRead,
    MemberWallchartDateRead,
    MemberWallchartHolidayRead,
    MemberWallchartPersonRead,
    MemberWallchartRead,
    MemberWallchartState,
    MemberWeekdayCountsRead,
    MemberWorkspaceRead,
    MemberYearSummaryRead,
)


def _workspace_name(session: Session, workspace_id: int) -> str:
    name = session.scalar(select(Workspace.name).where(Workspace.id == workspace_id))
    if name is None:
        raise ApiError(
            status_code=404,
            code="workspace_not_found",
            message="The selected workspace could not be found",
        )
    return name


def _leave_year(year: LeaveYear) -> MemberLeaveYearRead:
    return MemberLeaveYearRead(
        id=year.id,
        start_date=year.start_date,
        end_date=year.end_date,
        employment_start=year.employment_start,
        employment_end=year.employment_end,
    )


def _position(value: object) -> MemberBalancePositionRead | None:
    if value is None:
        return None
    return MemberBalancePositionRead.model_validate(value, from_attributes=True)


def _selected_year(
    session: Session, consultant_id: int, leave_year_id: int
) -> MemberYearSummaryRead:
    summary = get_summary(session, consultant_id, leave_year_id, include_audit=False)
    recommendation = summary.entitlement.recommendation
    application = summary.entitlement.application
    return MemberYearSummaryRead(
        leave_year=MemberLeaveYearRead.model_validate(
            summary.leave_year.model_dump(exclude={"consultant_id"})
        ),
        job_plans=tuple(
            MemberJobPlanRead(
                effective_from=plan.effective_from,
                effective_until=plan.effective_until,
                cycle_anchor_date=plan.cycle_anchor_date,
                week_count=plan.week_count,
                contracted_pas=plan.contracted_pas,
                dcc_pas=plan.dcc_pas,
                spa_pas=plan.spa_pas,
                other_pas=plan.other_pas,
                hours_per_pa=plan.hours_per_pa,
                days=tuple(
                    MemberJobPlanDayRead.model_validate(day.model_dump()) for day in plan.days
                ),
            )
            for plan in summary.job_plans
        ),
        entitlement=MemberEntitlementRead(
            recommendation=(
                MemberEntitlementRecommendationRead(
                    inputs=recommendation.inputs,
                    base_entitlement=recommendation.base_entitlement,
                    public_holiday_entitlement=recommendation.public_holiday_entitlement,
                    recommended_entitlement=recommendation.recommended_entitlement,
                    components=recommendation.components,
                    trace=tuple(
                        MemberEntitlementTraceRead(
                            description=step.description,
                            amount=step.amount,
                            effective_date=step.effective_date,
                        )
                        for step in recommendation.trace
                    ),
                )
                if recommendation
                else None
            ),
            application=(
                MemberAppliedEntitlementRead(
                    mode=application.mode,
                    entitlement=application.entitlement,
                    reason=application.reason,
                    updated_at=application.updated_at,
                )
                if application
                else None
            ),
        ),
        carry_forward=MemberCarryForwardRead(
            dcc_hours=summary.carry_forward.dcc_hours,
            spa_hours=summary.carry_forward.spa_hours,
            total_hours=summary.carry_forward.total_hours,
        ),
        allocation_source=summary.allocation_source,
        job_plan_periods=tuple(
            MemberJobPlanPeriodRead.model_validate(period.model_dump(exclude={"job_plan_id"}))
            for period in summary.job_plan_periods
        ),
        holidays=tuple(
            MemberHolidayRead(
                holiday_date=item.holiday_date,
                name=item.name,
                basis=item.basis.value,
                entitlement_hours=item.entitlement_hours,
                dcc_deduction_hours=item.dcc_deduction_hours,
                spa_deduction_hours=item.spa_deduction_hours,
            )
            for item in summary.planning.holidays
        ),
        bookings=tuple(
            MemberBookingRead(
                id=booking.id,
                start_date=booking.start_date,
                end_date=booking.end_date,
                state=booking.state.value,
                note=booking.note,
                cancellation_requested_at=booking.cancellation_requested_at,
                days=tuple(
                    MemberLeaveDayRead(
                        leave_date=day.leave_date,
                        deduction=day.deduction,
                        override_reason=day.override_reason,
                        public_holiday_name=day.public_holiday_name,
                    )
                    for day in booking.days
                ),
            )
            for booking in summary.planning.bookings
        ),
        balances=MemberBalanceViewsRead(
            requested=_position(summary.balances.requested),
            approved=_position(summary.balances.approved),
        ),
        weekday_counts=MemberWeekdayCountsRead.model_validate(summary.weekday_counts.model_dump()),
        warnings=summary.warnings,
    )


def _linked_consultant_id(access: WorkspaceAccess) -> int:
    if access.linked_consultant_id is None:
        raise ApiError(
            status_code=403,
            code="member_link_required",
            message="A consultant link is required",
        )
    return access.linked_consultant_id


def preview_leave_request(
    session: Session,
    access: WorkspaceAccess,
    leave_year_id: int,
    details: LeaveRequestWrite,
) -> LeavePreviewRead:
    return leave_booking_service.preview_request(
        session, _linked_consultant_id(access), leave_year_id, details
    )


def submit_leave_request(
    session: Session,
    access: WorkspaceAccess,
    leave_year_id: int,
    details: LeaveRequestWrite,
) -> MemberWorkspaceRead:
    consultant_id = _linked_consultant_id(access)
    leave_booking_service.submit_request(session, consultant_id, leave_year_id, details)
    return workspace(session, access, leave_year_id)


def cancel_leave_request(
    session: Session,
    access: WorkspaceAccess,
    leave_year_id: int,
    booking_id: int,
) -> MemberWorkspaceRead:
    consultant_id = _linked_consultant_id(access)
    leave_booking_service.cancel_member_request(
        session, consultant_id, leave_year_id, booking_id
    )
    return workspace(session, access, leave_year_id)


def request_leave_cancellation(
    session: Session,
    access: WorkspaceAccess,
    leave_year_id: int,
    booking_id: int,
) -> MemberWorkspaceRead:
    consultant_id = _linked_consultant_id(access)
    leave_booking_service.request_approved_cancellation(
        session, consultant_id, leave_year_id, booking_id
    )
    return workspace(session, access, leave_year_id)


def workspace(
    session: Session, access: WorkspaceAccess, leave_year_id: int | None
) -> MemberWorkspaceRead:
    name = _workspace_name(session, access.workspace_id)
    consultant_id = access.linked_consultant_id
    if consultant_id is None:
        return MemberWorkspaceRead(state="waiting", workspace_name=name)

    consultant = session.scalar(
        select(Consultant).where(
            Consultant.id == consultant_id,
            Consultant.workspace_id == access.workspace_id,
        )
    )
    if consultant is None:
        return MemberWorkspaceRead(state="waiting", workspace_name=name)

    years = leave_year_service.list_leave_years(session, consultant_id)
    selected = None
    if years:
        selected_id = leave_year_id if leave_year_id is not None else years[0].id
        if not any(year.id == selected_id for year in years):
            raise ApiError(
                status_code=404,
                code="leave_year_not_found",
                message="The leave year could not be found",
            )
        selected = _selected_year(session, consultant_id, selected_id)

    return MemberWorkspaceRead(
        state="linked",
        workspace_name=name,
        consultant=MemberConsultantRead(name=consultant.name, post_title=consultant.post_title),
        leave_years=tuple(_leave_year(year) for year in years),
        selected_year=selected,
    )


def wallchart(session: Session, access: WorkspaceAccess, month: date) -> MemberWallchartRead:
    _linked_consultant_id(access)

    month_start = month.replace(day=1)
    month_end = month_start.replace(day=monthrange(month_start.year, month_start.month)[1])
    consultants = tuple(
        session.scalars(
            select(Consultant)
            .where(
                Consultant.workspace_id == access.workspace_id,
                Consultant.archived_at.is_(None),
            )
            .order_by(Consultant.name, Consultant.id)
        )
    )
    states_by_consultant: dict[int, dict[date, MemberWallchartState]] = {
        item.id: {} for item in consultants
    }
    state_priority = {"requested": 0, "approved": 1}
    booking_rows = session.execute(
        select(
            LeaveYear.consultant_id,
            LeaveBookingRecord.start_date,
            LeaveBookingRecord.end_date,
            LeaveBookingRecord.state,
        )
        .join(LeaveBookingRecord, LeaveBookingRecord.leave_year_id == LeaveYear.id)
        .join(Consultant, Consultant.id == LeaveYear.consultant_id)
        .where(
            Consultant.workspace_id == access.workspace_id,
            Consultant.archived_at.is_(None),
            LeaveBookingRecord.state != "cancelled",
            LeaveBookingRecord.start_date <= month_end,
            LeaveBookingRecord.end_date >= month_start,
        )
    )
    for consultant_id, booking_start, booking_end, state in booking_rows:
        start = max(booking_start, month_start)
        end = min(booking_end, month_end)
        consultant_states = states_by_consultant[consultant_id]
        booking_state = cast(MemberWallchartState, state)
        for offset in range((end - start).days + 1):
            leave_date = start + timedelta(days=offset)
            existing = consultant_states.get(leave_date)
            if existing is None or state_priority[booking_state] > state_priority[existing]:
                consultant_states[leave_date] = booking_state

    holidays = tuple(
        holiday
        for holiday in resolved_holidays(holiday_service.active_calendar(session))
        if month_start <= holiday.holiday_date <= month_end
    )
    return MemberWallchartRead(
        month=month_start,
        holidays=tuple(
            MemberWallchartHolidayRead(holiday_date=item.holiday_date, name=item.name)
            for item in holidays
        ),
        people=tuple(
            MemberWallchartPersonRead(
                display_name=item.name,
                leave_dates=tuple(
                    MemberWallchartDateRead(leave_date=leave_date, state=state)
                    for leave_date, state in sorted(states_by_consultant[item.id].items())
                ),
            )
            for item in consultants
        ),
    )
