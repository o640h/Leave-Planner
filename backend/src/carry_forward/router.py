"""Consultant-year carry-forward routes."""

from fastapi import APIRouter

from dependencies import DatabaseSession

from . import service
from .schemas import CarryForwardRead, CarryForwardWrite

router = APIRouter(
    prefix="/api/consultants/{consultant_id}/leave-years/{leave_year_id}/carry-forward",
    tags=["carry forward"],
)


@router.get("", response_model=CarryForwardRead)
def get_carry_forward(
    consultant_id: int, leave_year_id: int, session: DatabaseSession
) -> CarryForwardRead:
    return service.get_carry_forward(session, consultant_id, leave_year_id)


@router.put("", response_model=CarryForwardRead)
def set_carry_forward(
    consultant_id: int,
    leave_year_id: int,
    details: CarryForwardWrite,
    session: DatabaseSession,
) -> CarryForwardRead:
    return service.set_carry_forward(session, consultant_id, leave_year_id, details)
