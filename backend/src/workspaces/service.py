"""Workspace membership resolution and request-scoped ownership helpers."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from authentication.models import User

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


def membership_for_user(session: Session, user_id: int) -> WorkspaceMembership | None:
    memberships = tuple(
        session.scalars(
            select(WorkspaceMembership)
            .where(WorkspaceMembership.user_id == user_id)
            .order_by(WorkspaceMembership.id)
            .limit(2)
        )
    )
    return memberships[0] if len(memberships) == 1 else None


def ensure_initial_membership(session: Session, user: User) -> WorkspaceMembership:
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
    return membership


def bind_workspace(session: Session, access: WorkspaceAccess) -> None:
    session.info[WORKSPACE_INFO_KEY] = access


def current_access(session: Session) -> WorkspaceAccess:
    access = session.info.get(WORKSPACE_INFO_KEY)
    if isinstance(access, WorkspaceAccess):
        return access

    workspace_ids = tuple(session.scalars(select(Workspace.id).order_by(Workspace.id).limit(2)))
    if workspace_ids == (INITIAL_WORKSPACE_ID,):
        return WorkspaceAccess(
            user_id=0,
            actor_label="System",
            workspace_id=INITIAL_WORKSPACE_ID,
            role=ADMIN_ROLE,
        )
    raise RuntimeError("A workspace must be bound before accessing private data")


def current_workspace_id(session: Session) -> int:
    return current_access(session).workspace_id
