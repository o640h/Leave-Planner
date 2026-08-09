"""FastAPI routes for consultant leave years."""

from fastapi import APIRouter, status

from dependencies import DatabaseSession
from removal import RemovalCommand, RemovalImpact, RemovalResult

from . import service
from .models import LeaveYear
from .schemas import LeaveYearCreate, LeaveYearRead, LeaveYearUpdate

router = APIRouter(
    prefix="/api/consultants/{consultant_id}/leave-years",
    tags=["leave years"],
)


@router.get("", response_model=list[LeaveYearRead])
def list_leave_years(
    consultant_id: int,
    session: DatabaseSession,
) -> tuple[LeaveYear, ...]:
    return service.list_leave_years(session, consultant_id)


@router.post(
    "",
    response_model=LeaveYearRead,
    status_code=status.HTTP_201_CREATED,
)
def create_leave_year(
    consultant_id: int,
    details: LeaveYearCreate,
    session: DatabaseSession,
) -> LeaveYear:
    return service.create_leave_year(session, consultant_id, details)


@router.put("/{leave_year_id}", response_model=LeaveYearRead)
def update_leave_year(
    consultant_id: int,
    leave_year_id: int,
    details: LeaveYearUpdate,
    session: DatabaseSession,
) -> LeaveYear:
    return service.update_leave_year(
        session,
        consultant_id,
        leave_year_id,
        details,
    )


@router.get("/{leave_year_id}/removal-impact", response_model=RemovalImpact)
def removal_impact(
    consultant_id: int,
    leave_year_id: int,
    session: DatabaseSession,
) -> RemovalImpact:
    return service.removal_impact(session, consultant_id, leave_year_id)


@router.post("/{leave_year_id}/remove", response_model=RemovalResult)
def remove_leave_year(
    consultant_id: int,
    leave_year_id: int,
    command: RemovalCommand,
    session: DatabaseSession,
) -> RemovalResult:
    return service.remove_leave_year(session, consultant_id, leave_year_id, command)
