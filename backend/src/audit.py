"""Small append-only audit-event foundation."""

import json
from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from database import Base


class AuditEvent(Base):
    """One recorded change to operator-maintained information."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
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

    session.add(
        AuditEvent(
            consultant_id=consultant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            details=json.dumps(details, sort_keys=True),
        )
    )
