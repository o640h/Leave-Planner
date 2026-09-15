"""Workspace membership, selection, and request-scoped database context."""

from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from authentication.models import User, UserSession

from .models import (
    ADMIN_ROLE,
    INITIAL_WORKSPACE_ID,
    INITIAL_WORKSPACE_NAME,
    Workspace,
    WorkspaceMembership,
)

WORKSPACE_INFO_KEY = "workspace_access"


@dataclass(frozen=True)
class WorkspaceAccess:
    user_id: int
    actor_label: str
    workspace_id: int
    role: str
    linked_consultant_id: int | None = None


@dataclass(frozen=True)
class AvailableWorkspace:
    id: int
    name: str
    role: str
    linked_consultant_id: int | None


@dataclass(frozen=True)
class WorkspaceContext:
    memberships: tuple[AvailableWorkspace, ...]
    active_workspace_id: int | None
    state: str


def _set_local_context(session: Session, key: str, value: int) -> None:
    if session.get_bind().dialect.name == "postgresql":
        session.execute(
            text("SELECT set_config(:key, :value, true)"),
            {"key": key, "value": str(value)},
        )


def bind_account(session: Session, user_id: int) -> None:
    """Bind the authenticated account before membership discovery under PostgreSQL RLS."""

    _set_local_context(session, "leave_planner.user_id", user_id)


def memberships_for_user(session: Session, user_id: int) -> tuple[AvailableWorkspace, ...]:
    bind_account(session, user_id)
    rows = session.execute(
        select(WorkspaceMembership, Workspace)
        .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
        .where(WorkspaceMembership.user_id == user_id)
        .order_by(Workspace.name, Workspace.id)
    )
    return tuple(
        AvailableWorkspace(
            id=workspace.id,
            name=workspace.name,
            role=membership.role,
            linked_consultant_id=membership.linked_consultant_id,
        )
        for membership, workspace in rows
    )


def initial_workspace_id(session: Session, user: User) -> int | None:
    memberships = memberships_for_user(session, user.id)
    authorised_ids = {membership.id for membership in memberships}
    if user.last_workspace_id in authorised_ids:
        return user.last_workspace_id
    if len(memberships) == 1:
        user.last_workspace_id = memberships[0].id
        return memberships[0].id
    return None


def workspace_context(
    session: Session, user_id: int, active_workspace_id: int | None
) -> WorkspaceContext:
    memberships = memberships_for_user(session, user_id)
    authorised_ids = {membership.id for membership in memberships}
    active = active_workspace_id if active_workspace_id in authorised_ids else None
    if not memberships:
        state = "onboarding"
    elif active is None:
        state = "selection_required"
    else:
        state = "active"
    return WorkspaceContext(
        memberships=memberships,
        active_workspace_id=active,
        state=state,
    )


def membership_for_user(
    session: Session, user_id: int, workspace_id: int
) -> WorkspaceMembership | None:
    bind_account(session, user_id)
    return session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
    )


def select_workspace(
    session: Session,
    *,
    user_id: int,
    user_session_id: int,
    workspace_id: int,
) -> WorkspaceMembership | None:
    membership = membership_for_user(session, user_id, workspace_id)
    if membership is None:
        return None

    stored_session = session.scalar(
        select(UserSession)
        .where(UserSession.id == user_session_id, UserSession.user_id == user_id)
        .with_for_update()
    )
    user = session.get(User, user_id)
    if stored_session is None or user is None:
        return None
    stored_session.active_workspace_id = workspace_id
    user.last_workspace_id = workspace_id
    return membership


def ensure_initial_membership(session: Session, user: User) -> WorkspaceMembership:
    """Retain the focused-test scaffold until the first-Owner transition replaces it."""

    workspace = session.get(Workspace, INITIAL_WORKSPACE_ID)
    if workspace is None:
        workspace = Workspace(id=INITIAL_WORKSPACE_ID, name=INITIAL_WORKSPACE_NAME)
        session.add(workspace)
        session.flush()

    membership = session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == user.id,
        )
    )
    if membership is None:
        membership = WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=ADMIN_ROLE,
        )
        session.add(membership)
        session.flush()
    user.last_workspace_id = workspace.id
    return membership


def bind_workspace(session: Session, access: WorkspaceAccess) -> None:
    bind_account(session, access.user_id)
    _set_local_context(session, "leave_planner.workspace_id", access.workspace_id)
    session.info[WORKSPACE_INFO_KEY] = access


def current_access(session: Session) -> WorkspaceAccess:
    access = session.info.get(WORKSPACE_INFO_KEY)
    if isinstance(access, WorkspaceAccess):
        return access
    raise RuntimeError("A workspace must be bound before accessing private data")


def current_workspace_id(session: Session) -> int:
    return current_access(session).workspace_id
