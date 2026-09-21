"""Authenticated endpoints for the restricted Member workspace."""

from datetime import date
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request, status

from authentication.dependencies import runtime_settings
from authentication.email_delivery import EmailSender
from dependencies import DatabaseSession
from http_security import enforce_account_action_limit
from leave_bookings import notifications
from leave_bookings.schemas import LeavePreviewRead, LeaveRequestWrite
from workspaces.dependencies import require_member_workspace_request
from workspaces.service import WorkspaceAccess

from . import service
from .schemas import MemberWallchartRead, MemberWorkspaceRead

router = APIRouter(prefix="/api/member", tags=["member-workspace"])
MemberAccess = Annotated[WorkspaceAccess, Depends(require_member_workspace_request)]


def _notify_operators(
    request: Request,
    session: DatabaseSession,
    access: WorkspaceAccess,
    event: notifications.OperatorEvent,
) -> None:
    notifications.notify_operators(
        session,
        cast(EmailSender, request.app.state.email_sender),
        workspace_id=access.workspace_id,
        origin=runtime_settings(request).public_origin or str(request.base_url).rstrip("/"),
        event=event,
    )
    session.commit()


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
    request: Request,
    session: DatabaseSession,
    access: MemberAccess,
) -> MemberWorkspaceRead:
    enforce_account_action_limit(request, access.user_id, "member-leave-request")
    result = service.submit_leave_request(session, access, leave_year_id, details)
    session.commit()
    _notify_operators(request, session, access, "submitted")
    return result


@router.post(
    "/leave-years/{leave_year_id}/bookings/{booking_id}/cancel",
    response_model=MemberWorkspaceRead,
)
def cancel_leave_request(
    leave_year_id: int,
    booking_id: int,
    request: Request,
    session: DatabaseSession,
    access: MemberAccess,
) -> MemberWorkspaceRead:
    enforce_account_action_limit(request, access.user_id, "member-leave-request")
    result = service.cancel_leave_request(
        session, access, leave_year_id, booking_id
    )
    session.commit()
    _notify_operators(request, session, access, "withdrawn")
    return result


@router.post(
    "/leave-years/{leave_year_id}/bookings/{booking_id}/request-cancellation",
    response_model=MemberWorkspaceRead,
)
def request_leave_cancellation(
    leave_year_id: int,
    booking_id: int,
    request: Request,
    session: DatabaseSession,
    access: MemberAccess,
) -> MemberWorkspaceRead:
    enforce_account_action_limit(request, access.user_id, "member-leave-request")
    result = service.request_leave_cancellation(
        session, access, leave_year_id, booking_id
    )
    session.commit()
    _notify_operators(request, session, access, "cancellation_requested")
    return result
