"""Authenticated endpoints for the restricted Member workspace."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from dependencies import DatabaseSession
from leave_bookings.schemas import LeavePreviewRead, LeaveRequestWrite
from workspaces.dependencies import require_member_workspace_request
from workspaces.service import WorkspaceAccess

from . import service
from .schemas import MemberWallchartRead, MemberWorkspaceRead

router = APIRouter(prefix="/api/member", tags=["member-workspace"])
MemberAccess = Annotated[WorkspaceAccess, Depends(require_member_workspace_request)]


@router.get("/workspace", response_model=MemberWorkspaceRead)
def read_workspace(
    session: DatabaseSession,
    access: MemberAccess,
    leave_year_id: int | None = Query(default=None),
) -> MemberWorkspaceRead:
    return service.workspace(session, access, leave_year_id)


@router.get("/wallchart", response_model=MemberWallchartRead)
def read_wallchart(
    session: DatabaseSession,
    month: date,
    access: MemberAccess,
) -> MemberWallchartRead:
    return service.wallchart(session, access, month)


@router.post(
    "/leave-years/{leave_year_id}/requests/preview",
    response_model=LeavePreviewRead,
)
def preview_leave_request(
    leave_year_id: int,
    details: LeaveRequestWrite,
    session: DatabaseSession,
    access: MemberAccess,
) -> LeavePreviewRead:
    return service.preview_leave_request(session, access, leave_year_id, details)


@router.post(
    "/leave-years/{leave_year_id}/requests",
    response_model=MemberWorkspaceRead,
    status_code=status.HTTP_201_CREATED,
)
def submit_leave_request(
    leave_year_id: int,
    details: LeaveRequestWrite,
    session: DatabaseSession,
    access: MemberAccess,
) -> MemberWorkspaceRead:
    return service.submit_leave_request(session, access, leave_year_id, details)


@router.post(
    "/leave-years/{leave_year_id}/bookings/{booking_id}/cancel",
    response_model=MemberWorkspaceRead,
)
def cancel_leave_request(
    leave_year_id: int,
    booking_id: int,
    session: DatabaseSession,
    access: MemberAccess,
) -> MemberWorkspaceRead:
    return service.cancel_leave_request(
        session, access, leave_year_id, booking_id
    )


@router.post(
    "/leave-years/{leave_year_id}/bookings/{booking_id}/request-cancellation",
    response_model=MemberWorkspaceRead,
)
def request_leave_cancellation(
    leave_year_id: int,
    booking_id: int,
    session: DatabaseSession,
    access: MemberAccess,
) -> MemberWorkspaceRead:
    return service.request_leave_cancellation(
        session, access, leave_year_id, booking_id
    )
