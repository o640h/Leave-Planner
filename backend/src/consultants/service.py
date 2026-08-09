"""Database operations for the consultant directory."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from audit import record_audit_event
from errors import ApiError
from removal import RemovalCommand, RemovalImpact, RemovalResult

from .models import Consultant
from .schemas import ConsultantCreate, ConsultantUpdate


def list_consultants(session: Session) -> tuple[Consultant, ...]:
    statement = (
        select(Consultant)
        .where(Consultant.archived_at.is_(None))
        .order_by(Consultant.name, Consultant.id)
    )
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


def archive_impact(session: Session, consultant_id: int) -> RemovalImpact:
    """Describe retained records before a consultant leaves the active directory."""

    from annual_entitlement.persistence import AppliedEntitlementRecord
    from job_plans.persistence import JobPlanRecord
    from leave_years.models import LeaveYear

    consultant = get_consultant(session, consultant_id)
    leave_year_ids = select(LeaveYear.id).where(LeaveYear.consultant_id == consultant_id)
    leave_year_count = session.scalar(
        select(func.count()).select_from(LeaveYear).where(LeaveYear.consultant_id == consultant_id)
    ) or 0
    job_plan_count = session.scalar(
        select(func.count())
        .select_from(JobPlanRecord)
        .where(JobPlanRecord.leave_year_id.in_(leave_year_ids))
    ) or 0
    application_count = session.scalar(
        select(func.count())
        .select_from(AppliedEntitlementRecord)
        .where(AppliedEntitlementRecord.leave_year_id.in_(leave_year_ids))
    ) or 0

    return RemovalImpact(
        resource_name=consultant.name,
        action="archive",
        confirmation_text=consultant.name,
        consequences=(
            "The consultant will disappear from the active directory.",
            f"{leave_year_count} leave year(s) will be retained.",
            f"{job_plan_count} job plan(s) will be retained.",
            f"{application_count} applied entitlement record(s) will be retained.",
        ),
    )


def archive_consultant(
    session: Session,
    consultant_id: int,
    command: RemovalCommand,
) -> RemovalResult:
    """Archive a consultant while preserving every dependent record."""

    consultant = get_consultant(session, consultant_id)
    if consultant.archived_at is not None:
        raise ApiError(
            status_code=409,
            code="consultant_already_archived",
            message="This consultant is already archived.",
        )
    if command.confirmation.strip() != consultant.name:
        raise ApiError(
            status_code=422,
            code="confirmation_mismatch",
            message="Enter the consultant's full name exactly to confirm archiving.",
        )

    consultant.archived_at = datetime.now(UTC).replace(tzinfo=None)
    record_audit_event(
        session,
        consultant_id=consultant.id,
        entity_type="consultant",
        entity_id=consultant.id,
        action="archived",
        details={"name": consultant.name, "archived_at": consultant.archived_at.isoformat()},
    )
    session.flush()
    return RemovalResult(message=f"{consultant.name} was archived.")
