"""Consultant-year planning and leave booking routes."""

from fastapi import APIRouter

from dependencies import DatabaseSession

from . import service
from .schemas import LeaveBookingWrite, LeavePreviewRead, PlanningRead

router = APIRouter(
    prefix="/api/consultants/{consultant_id}/leave-years/{leave_year_id}",
    tags=["leave bookings"],
)


@router.get("/planning", response_model=PlanningRead)
def get_planning(
    consultant_id: int, leave_year_id: int, session: DatabaseSession
) -> PlanningRead:
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

