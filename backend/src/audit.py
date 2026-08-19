"""Small append-only audit-event foundation."""

import json
from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from database import Base
from workspaces.service import current_access


class AuditEvent(Base):
    """One recorded change to operator-maintained information."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_label: Mapped[str] = mapped_column(String(100), nullable=False)
    consultant_id: Mapped[int] = mapped_column(
        ForeignKey("consultants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(),
        server_default=func.current_timestamp(),
        nullable=False,
    )


def record_audit_event(
    session: Session,
    *,
    consultant_id: int,
    entity_type: str,
    entity_id: int,
    action: str,
    details: Mapping[str, object],
) -> None:
    """Append one JSON-backed audit event to the current transaction."""

    access = current_access(session)
    session.add(
        AuditEvent(
            workspace_id=access.workspace_id,
            actor_user_id=access.user_id or None,
            actor_label=access.actor_label,
            consultant_id=consultant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            details=json.dumps(details, sort_keys=True),
        )
    )


def list_audit_events(
    session: Session, consultant_id: int, *, limit: int = 50
) -> tuple[AuditEvent, ...]:
    """Return the consultant's latest append-only changes."""

    access = current_access(session)
    statement = (
        select(AuditEvent)
        .where(
            AuditEvent.workspace_id == access.workspace_id,
            AuditEvent.consultant_id == consultant_id,
        )
        .order_by(AuditEvent.recorded_at.desc(), AuditEvent.id.desc())
        .limit(limit)
    )
    return tuple(session.scalars(statement))
