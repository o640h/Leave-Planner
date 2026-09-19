"""Workspace membership, selection, and request-scoped database context."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from authentication.models import User, UserSession
from authentication.service import (
    account_for_email,
    create_account,
    password_is_valid,
    record_security_event,
    revoke_all_sessions,
)

from .models import (
    ACTIVE_WORKSPACE,
    OWNER_ROLE,
    Workspace,
    WorkspaceMembership,
)

WORKSPACE_INFO_KEY = "workspace_access"
_TENANT_DATA_TABLES = ("consultants", "holiday_corrections", "audit_events")


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
    revision: int | None


@dataclass(frozen=True)
class InitialOwnerWorkspace:
    account: User
    workspace: Workspace
    created: bool


def _workspace_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise ValueError("Enter a workspace name")
    if len(name) > 160:
        raise ValueError("Workspace name must contain no more than 160 characters")
    return name


def _tenant_data_counts(session: Session) -> dict[str, int]:
    counts = {
        table: int(session.scalar(text(f"SELECT COUNT(*) FROM {table}")) or 0)
        for table in _TENANT_DATA_TABLES
    }
    return {table: count for table, count in counts.items() if count}


def create_initial_owner_workspace(
    session: Session,
    *,
    email: str,
    password: str,
    workspace_name: str,
    display_name: str | None = None,
) -> InitialOwnerWorkspace:
    """Create the first empty workspace or verify the already-completed transition."""

    name = _workspace_name(workspace_name)
    account = account_for_email(session, email, for_update=True)
    memberships = tuple(
        session.execute(
            select(WorkspaceMembership, Workspace).join(
                Workspace, Workspace.id == WorkspaceMembership.workspace_id
            )
        )
    )

    if memberships:
        owned = tuple(
            (membership, workspace)
            for membership, workspace in memberships
            if account is not None
            and membership.user_id == account.id
            and membership.role == OWNER_ROLE
        )
        if len(owned) != 1 or owned[0][1].name != name or not password_is_valid(account, password):
            raise ValueError("The first Owner workspace is already configured")
        assert account is not None
        return InitialOwnerWorkspace(account=account, workspace=owned[0][1], created=False)

    occupied = _tenant_data_counts(session)
    if occupied:
        detail = ", ".join(f"{table}={count}" for table, count in sorted(occupied.items()))
        raise ValueError(
            f"Cannot create the first Owner while legacy business data remains ({detail})"
        )

    if account is None:
        if display_name is None:
            raise ValueError("Enter a display name for the new account")
        account = create_account(
            session,
            display_name=display_name,
            email=email,
            password=password,
            verified_at=datetime.now(UTC),
        )
    elif not password_is_valid(account, password):
        raise ValueError("The existing account password could not be verified")

    # Migration 0014 necessarily left an empty scaffold. It is discarded, never inherited.
    session.execute(delete(Workspace))
    workspace = Workspace(name=name)
    session.add(workspace)
    session.flush()
    session.add(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=account.id,
            role=OWNER_ROLE,
        )
    )
    account.last_workspace_id = workspace.id
    revoke_all_sessions(session, account.id, now=datetime.now(UTC))
    record_security_event(
        session,
        "initial_owner_workspace_created",
        user_id=account.id,
        actor_label="Server Owner",
        details={"workspace_id": workspace.id},
    )
    session.flush()
    return InitialOwnerWorkspace(account=account, workspace=workspace, created=True)


def create_owned_workspace(
    session: Session,
    *,
    user_id: int,
    user_session_id: int,
    workspace_name: str,
    owned_workspace_limit: int,
) -> WorkspaceContext:
    """Create and select one explicitly requested empty Owner workspace."""

    name = _workspace_name(workspace_name)
    bind_account(session, user_id)
    account = session.scalar(select(User).where(User.id == user_id).with_for_update())
    if account is None:
        raise RuntimeError("The workspace Owner account no longer exists")
    owned_count = session.scalar(
        select(func.count())
        .select_from(WorkspaceMembership)
        .where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.role == OWNER_ROLE,
        )
    )
    if int(owned_count or 0) >= owned_workspace_limit:
        raise ValueError("This account has reached its workspace creation limit")

    workspace = Workspace(name=name)
    if session.get_bind().dialect.name == "postgresql":
        workspace.id = int(
            session.scalar(text("SELECT nextval(pg_get_serial_sequence('workspaces', 'id'))")) or 0
        )
        _set_local_context(session, "leave_planner.workspace_id", workspace.id)
    session.add(workspace)
    session.flush()
    session.add(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user_id,
            role=OWNER_ROLE,
        )
    )
    session.flush()
    membership = select_workspace(
        session,
        user_id=user_id,
        user_session_id=user_session_id,
        workspace_id=workspace.id,
    )
    if membership is None:
        raise RuntimeError("The new workspace could not be selected")
    record_security_event(
        session,
        "workspace_created",
        user_id=user_id,
        actor_label=account.display_name,
        details={"workspace_id": workspace.id},
    )
    return workspace_context(session, user_id, workspace.id)


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
        .where(Workspace.status == ACTIVE_WORKSPACE)
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
    revision = (
        session.scalar(select(Workspace.revision).where(Workspace.id == active))
        if active is not None
        else None
    )
    return WorkspaceContext(
        memberships=memberships,
        active_workspace_id=active,
        state=state,
        revision=revision,
    )


def membership_for_user(
    session: Session, user_id: int, workspace_id: int
) -> WorkspaceMembership | None:
    bind_account(session, user_id)
    return session.scalar(
        select(WorkspaceMembership)
        .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
        .where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.workspace_id == workspace_id,
            Workspace.status == ACTIVE_WORKSPACE,
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
