"""Database operations for the consultant directory."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from errors import ApiError

from .models import Consultant
from .schemas import ConsultantCreate, ConsultantUpdate


def list_consultants(session: Session) -> tuple[Consultant, ...]:
    statement = select(Consultant).order_by(Consultant.name, Consultant.id)
    return tuple(session.scalars(statement))


def get_consultant(session: Session, consultant_id: int) -> Consultant:
    consultant = session.get(Consultant, consultant_id)
    if consultant is None:
        raise ApiError(
            status_code=404,
            code="consultant_not_found",
            message="The requested consultant could not be found.",
        )
    return consultant


def create_consultant(session: Session, details: ConsultantCreate) -> Consultant:
    consultant = Consultant(**details.model_dump())
    session.add(consultant)
    session.flush()
    session.refresh(consultant)
    return consultant


def update_consultant(
    session: Session, consultant_id: int, details: ConsultantUpdate
) -> Consultant:
    consultant = get_consultant(session, consultant_id)
    consultant.name = details.name
    consultant.post_title = details.post_title
    session.flush()
    session.refresh(consultant)
    return consultant
