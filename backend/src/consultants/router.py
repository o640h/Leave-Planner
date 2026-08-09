"""FastAPI routes for the consultant directory."""

from fastapi import APIRouter, status

from dependencies import DatabaseSession
from removal import RemovalCommand, RemovalImpact, RemovalResult

from . import service
from .models import Consultant
from .schemas import ConsultantCreate, ConsultantRead, ConsultantUpdate

router = APIRouter(prefix="/api/consultants", tags=["consultants"])


@router.get("", response_model=list[ConsultantRead])
def list_consultants(session: DatabaseSession) -> tuple[Consultant, ...]:
    """List consultants in directory order."""

    return service.list_consultants(session)


@router.post(
    "",
    response_model=ConsultantRead,
    status_code=status.HTTP_201_CREATED,
)
def create_consultant(
    details: ConsultantCreate,
    session: DatabaseSession,
) -> Consultant:
    """Create a consultant from operator-entered information."""

    return service.create_consultant(session, details)


@router.get("/{consultant_id}", response_model=ConsultantRead)
def get_consultant(
    consultant_id: int,
    session: DatabaseSession,
) -> Consultant:
    """Return one consultant for editing."""

    return service.get_consultant(session, consultant_id)


@router.put("/{consultant_id}", response_model=ConsultantRead)
def update_consultant(
    consultant_id: int,
    details: ConsultantUpdate,
    session: DatabaseSession,
) -> Consultant:
    """Replace one consultant's editable information."""

    return service.update_consultant(session, consultant_id, details)


@router.get("/{consultant_id}/archive-impact", response_model=RemovalImpact)
def archive_impact(consultant_id: int, session: DatabaseSession) -> RemovalImpact:
    return service.archive_impact(session, consultant_id)


@router.post("/{consultant_id}/archive", response_model=RemovalResult)
def archive_consultant(
    consultant_id: int,
    command: RemovalCommand,
    session: DatabaseSession,
) -> RemovalResult:
    return service.archive_consultant(session, consultant_id, command)
