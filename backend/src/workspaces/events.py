"""Durable workspace activity events shared by workspace-scoped workflows."""

import json

from sqlalchemy.orm import Session

from .models import WorkspaceEvent
from .service import current_access


def record_workspace_event(
    session: Session,
    *,
    event_type: str,
    details: dict[str, object] | None = None,
) -> None:
    """Append one event using the authenticated workspace and actor."""

    access = current_access(session)
    session.add(
        WorkspaceEvent(
            workspace_id=access.workspace_id,
            actor_user_id=access.user_id or None,
            actor_label=access.actor_label,
            event_type=event_type,
            details=json.dumps(details or {}, sort_keys=True),
        )
    )
