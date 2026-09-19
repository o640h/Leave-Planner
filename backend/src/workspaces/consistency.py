"""Workspace-wide optimistic concurrency for shared mutable data."""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import Response
from sqlalchemy import event, inspect, select, update
from sqlalchemy.orm import Session

from errors import ApiError

from .live_updates import queue_invalidation
from .models import Workspace
from .service import WORKSPACE_INFO_KEY, WorkspaceAccess

EXPECTED_REVISION_KEY = "expected_workspace_revision"
REVISION_REQUIRED_KEY = "workspace_revision_required"
REVISION_ADVANCED_KEY = "workspace_revision_advanced"
REVISION_RESPONSE_KEY = "workspace_revision_response"

_TABLE_SCOPES: dict[str, frozenset[str]] = {
    "consultants": frozenset({"consultants", "planning", "member-workspace"}),
    "leave_years": frozenset({"consultants", "planning", "member-workspace"}),
    "job_plan_versions": frozenset({"consultants", "planning", "member-workspace"}),
    "job_plan_days": frozenset({"consultants", "planning", "member-workspace"}),
    "entitlement_recommendations": frozenset({"consultants", "member-workspace"}),
    "applied_entitlements": frozenset({"consultants", "planning", "member-workspace"}),
    "leave_year_adjustments": frozenset({"consultants", "planning", "member-workspace"}),
    "leave_bookings": frozenset({"consultants", "planning", "member-workspace"}),
    "leave_booking_days": frozenset({"consultants", "planning", "member-workspace"}),
    "holiday_corrections": frozenset(
        {"holidays", "consultants", "planning", "member-workspace"}
    ),
    "public_holiday_treatments": frozenset(
        {"holidays", "consultants", "planning", "member-workspace"}
    ),
    "holiday_calendar_versions": frozenset(
        {"holidays", "consultants", "planning", "member-workspace"}
    ),
    "holiday_calendar_events": frozenset(
        {"holidays", "consultants", "planning", "member-workspace"}
    ),
    "workspace_memberships": frozenset(
        {"workspace-management", "workspace-context", "member-workspace"}
    ),
    "workspace_invitations": frozenset({"workspace-management"}),
    "workspace_ownership_transfers": frozenset(
        {"workspace-management", "workspace-context"}
    ),
    "workspaces": frozenset({"workspace-management", "workspace-context"}),
}


def configure_request_revision(
    session: Session,
    raw_revision: str | None,
    *,
    required: bool,
    response: Response,
) -> None:
    """Capture the browser revision before any shared write is flushed."""

    expected: int | None = None
    if raw_revision is not None:
        try:
            expected = int(raw_revision.strip('"'))
        except ValueError as error:
            raise ApiError(
                status_code=400,
                code="invalid_workspace_revision",
                message="The workspace revision is invalid.",
            ) from error
        if expected < 1:
            raise ApiError(
                status_code=400,
                code="invalid_workspace_revision",
                message="The workspace revision is invalid.",
            )
    session.info[EXPECTED_REVISION_KEY] = expected
    session.info[REVISION_REQUIRED_KEY] = required
    session.info[REVISION_RESPONSE_KEY] = response


def _changed_scopes(session: Session) -> frozenset[str]:
    scopes: set[str] = set()
    for record in (*session.new, *session.dirty, *session.deleted):
        table = getattr(record, "__table__", None)
        if table is None or table.name not in _TABLE_SCOPES:
            continue
        if isinstance(record, Workspace) and record in session.dirty:
            changed = {
                attribute.key
                for attribute in inspect(record).attrs
                if attribute.history.has_changes()
            }
            if changed == {"revision"}:
                continue
        scopes.update(_TABLE_SCOPES[table.name])
    return frozenset(scopes)


def _current_revision(session: Session, workspace_id: int) -> int:
    revision = session.scalar(select(Workspace.revision).where(Workspace.id == workspace_id))
    if revision is None:
        raise ApiError(
            status_code=409,
            code="workspace_unavailable",
            message="This workspace is no longer available.",
        )
    return revision


def use_current_workspace_revision(session: Session, workspace: Workspace) -> None:
    """Use the target revision when a token action was not based on rendered workspace data."""

    session.info.pop(REVISION_ADVANCED_KEY, None)
    session.info[EXPECTED_REVISION_KEY] = workspace.revision


@event.listens_for(Session, "before_flush")
def enforce_workspace_revision(
    session: Session,
    _flush_context: object,
    _instances: Iterable[object] | None,
) -> None:
    """Conditionally advance the workspace revision in the write transaction."""

    if session.info.get(REVISION_ADVANCED_KEY):
        return
    access = session.info.get(WORKSPACE_INFO_KEY)
    if not isinstance(access, WorkspaceAccess):
        return
    scopes = _changed_scopes(session)
    if not scopes:
        return

    expected = session.info.get(EXPECTED_REVISION_KEY)
    if expected is None:
        if session.info.get(REVISION_REQUIRED_KEY):
            raise ApiError(
                status_code=428,
                code="workspace_revision_required",
                message="Reload this workspace before saving changes.",
            )
        expected = _current_revision(session, access.workspace_id)

    statement = (
        update(Workspace)
        .where(Workspace.id == access.workspace_id, Workspace.revision == expected)
        .values(revision=Workspace.revision + 1)
        .returning(Workspace.revision)
        .execution_options(synchronize_session="fetch")
    )
    revision = session.scalar(statement)
    if revision is None:
        raise ApiError(
            status_code=409,
            code="stale_workspace_data",
            message=(
                "This workspace changed in another session. "
                "Review the latest data and try again."
            ),
        )
    session.info[REVISION_ADVANCED_KEY] = True
    response = session.info.get(REVISION_RESPONSE_KEY)
    if isinstance(response, Response):
        response.headers["X-Workspace-Revision"] = str(revision)
    queue_invalidation(
        session,
        workspace_id=access.workspace_id,
        revision=revision,
        scopes=scopes,
    )
