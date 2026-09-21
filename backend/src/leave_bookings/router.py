"""Consultant-year planning and leave booking routes."""

from typing import cast

from fastapi import APIRouter, Request

from authentication.dependencies import runtime_settings
from authentication.email_delivery import EmailSender
from dependencies import DatabaseSession
from http_security import enforce_account_action_limit
from leave_years import service as leave_year_service
from workspaces.service import current_access

from . import notifications, service
from .schemas import (
    LeaveBookingWrite,
    LeavePreviewRead,
    LeaveRequestQueueRead,
    LeaveRequestReviewRead,
    PlanningRead,
)

router = APIRouter(
    prefix="/api/consultants/{consultant_id}/leave-years/{leave_year_id}",
    tags=["leave bookings"],
)
request_router = APIRouter(prefix="/api/leave-requests", tags=["leave requests"])


@request_router.get("", response_model=LeaveRequestQueueRead)
def get_request_queue(session: DatabaseSession) -> LeaveRequestQueueRead:
    return service.request_queue(session)


@router.get("/planning", response_model=PlanningRead)
def get_planning(consultant_id: int, leave_year_id: int, session: DatabaseSession) -> PlanningRead:
    return service.planning(session, consultant_id, leave_year_id)


@router.post("/bookings/preview", response_model=LeavePreviewRead)
def preview_booking(
    consultant_id: int,
    leave_year_id: int,
    details: LeaveBookingWrite,
    session: DatabaseSession,
) -> LeavePreviewRead:
    return service.preview_booking(session, consultant_id, leave_year_id, details)


@router.post("/bookings", response_model=PlanningRead, status_code=201)
def create_booking(
    consultant_id: int,
    leave_year_id: int,
    details: LeaveBookingWrite,
    session: DatabaseSession,
) -> PlanningRead:
    return service.create_booking(session, consultant_id, leave_year_id, details)


@router.post("/bookings/{booking_id}/preview", response_model=LeavePreviewRead)
def preview_booking_update(
    consultant_id: int,
    leave_year_id: int,
    booking_id: int,
    details: LeaveBookingWrite,
    session: DatabaseSession,
) -> LeavePreviewRead:
    leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    service._record(session, leave_year_id, booking_id)
    return service.preview_booking(
        session, consultant_id, leave_year_id, details, excluding_id=booking_id
    )


@router.put("/bookings/{booking_id}", response_model=PlanningRead)
def update_booking(
    consultant_id: int,
    leave_year_id: int,
    booking_id: int,
    details: LeaveBookingWrite,
    session: DatabaseSession,
) -> PlanningRead:
    return service.update_booking(session, consultant_id, leave_year_id, booking_id, details)


@router.post("/bookings/{booking_id}/cancel", response_model=PlanningRead)
def cancel_booking(
    consultant_id: int,
    leave_year_id: int,
    booking_id: int,
    session: DatabaseSession,
) -> PlanningRead:
    return service.cancel_booking(session, consultant_id, leave_year_id, booking_id)


@router.delete("/bookings/{booking_id}", response_model=PlanningRead)
def remove_booking(
    consultant_id: int,
    leave_year_id: int,
    booking_id: int,
    session: DatabaseSession,
) -> PlanningRead:
    return service.remove_booking(session, consultant_id, leave_year_id, booking_id)


@router.get("/bookings/{booking_id}/review", response_model=LeaveRequestReviewRead)
def review_booking_request(
    consultant_id: int,
    leave_year_id: int,
    booking_id: int,
    session: DatabaseSession,
) -> LeaveRequestReviewRead:
    return service.review_request(session, consultant_id, leave_year_id, booking_id)


@router.post("/bookings/{booking_id}/approve", response_model=PlanningRead)
def approve_booking_request(
    consultant_id: int,
    leave_year_id: int,
    booking_id: int,
    request: Request,
    session: DatabaseSession,
) -> PlanningRead:
    enforce_account_action_limit(
        request, current_access(session).user_id, "leave-request-decision"
    )
    result, requester_user_id = service.approve_request(
        session, consultant_id, leave_year_id, booking_id
    )
    session.commit()
    _notify_member(request, session, requester_user_id, "approved")
    return result


@router.post("/bookings/{booking_id}/reject", response_model=PlanningRead)
def reject_booking_request(
    consultant_id: int,
    leave_year_id: int,
    booking_id: int,
    request: Request,
    session: DatabaseSession,
) -> PlanningRead:
    enforce_account_action_limit(
        request, current_access(session).user_id, "leave-request-decision"
    )
    result, requester_user_id = service.reject_request(
        session, consultant_id, leave_year_id, booking_id
    )
    session.commit()
    _notify_member(request, session, requester_user_id, "rejected")
    return result


@router.post("/bookings/{booking_id}/approve-cancellation", response_model=PlanningRead)
def approve_booking_cancellation(
    consultant_id: int,
    leave_year_id: int,
    booking_id: int,
    request: Request,
    session: DatabaseSession,
) -> PlanningRead:
    enforce_account_action_limit(
        request, current_access(session).user_id, "leave-request-decision"
    )
    result, requester_user_id = service.approve_cancellation_request(
        session, consultant_id, leave_year_id, booking_id
    )
    session.commit()
    _notify_member(request, session, requester_user_id, "cancellation_approved")
    return result


@router.post("/bookings/{booking_id}/reject-cancellation", response_model=PlanningRead)
def reject_booking_cancellation(
    consultant_id: int,
    leave_year_id: int,
    booking_id: int,
    request: Request,
    session: DatabaseSession,
) -> PlanningRead:
    enforce_account_action_limit(
        request, current_access(session).user_id, "leave-request-decision"
    )
    result, requester_user_id = service.reject_cancellation_request(
        session, consultant_id, leave_year_id, booking_id
    )
    session.commit()
    _notify_member(request, session, requester_user_id, "cancellation_rejected")
    return result


def _notify_member(
    request: Request,
    session: DatabaseSession,
    requester_user_id: int | None,
    decision: notifications.MemberDecision,
) -> None:
    access = current_access(session)
    notifications.notify_member(
        session,
        cast(EmailSender, request.app.state.email_sender),
        workspace_id=access.workspace_id,
        requester_user_id=requester_user_id,
        origin=runtime_settings(request).public_origin or str(request.base_url).rstrip("/"),
        decision=decision,
    )
    session.commit()
