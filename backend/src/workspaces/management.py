"""Workspace people, invitation, ownership, and lifecycle orchestration."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Session

from authentication.account_actions import (
    INVITATION,
    INVITATION_LIFETIME,
    consume_action,
    issue_action,
    valid_action,
)
from authentication.models import AccountActionToken, User, UserSession
from authentication.service import AuthenticatedUser, normalise_email
from consultants.models import Consultant
from public_holidays.persistence import HolidayCorrectionRecord

from .consistency import use_current_workspace_revision
from .models import (
    ACCEPTED_INVITATION,
    ACCEPTED_TRANSFER,
    ACTIVE_WORKSPACE,
    ADMIN_ROLE,
    CANCELLED_TRANSFER,
    CLOSED_WORKSPACE,
    MEMBER_ROLE,
    OWNER_ROLE,
    PENDING_INVITATION,
    PENDING_TRANSFER,
    REVOKED_INVITATION,
    Workspace,
    WorkspaceEvent,
    WorkspaceInvitation,
    WorkspaceMembership,
    WorkspaceOwnershipTransfer,
)
from .service import WorkspaceAccess, bind_account, bind_workspace, membership_for_user

TRANSFER_LIFETIME = timedelta(days=7)
WORKSPACE_RECOVERY_LIFETIME = timedelta(days=30)


@dataclass(frozen=True)
class WorkspaceListItem:
    id: int
    name: str
    role: str
    status: str
    closed_at: datetime | None
    purge_after: datetime | None


@dataclass(frozen=True)
class WorkspacePerson:
    membership_id: int
    user_id: int
    public_id: str
    display_name: str
    display_email: str
    role: str
    linked_consultant_id: int | None
    linked_consultant_name: str | None


@dataclass(frozen=True)
class WorkspaceInvitationItem:
    id: int
    display_email: str
    role: str
    linked_consultant_id: int | None
    status: str
    expires_at: datetime


@dataclass(frozen=True)
class WorkspaceTransferItem:
    id: int
    from_user_id: int
    to_user_id: int
    to_display_name: str
    expires_at: datetime
    can_accept: bool


@dataclass(frozen=True)
class WorkspaceEventItem:
    id: int
    actor_label: str
    event_type: str
    details: dict[str, object]
    recorded_at: datetime


@dataclass(frozen=True)
class WorkspaceDetails:
    workspace: Workspace
    current_role: str
    people: tuple[WorkspacePerson, ...]
    invitations: tuple[WorkspaceInvitationItem, ...]
    consultants: tuple[tuple[int, str], ...]
    transfer: WorkspaceTransferItem | None
    events: tuple[WorkspaceEventItem, ...]


@dataclass(frozen=True)
class WorkspaceImpact:
    consultants: int
    pending_invitations: int
    has_operational_history: bool
    can_delete_immediately: bool


def _now() -> datetime:
    return datetime.now(UTC)


def _comparable(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _record_event(
    session: Session,
    *,
    workspace_id: int,
    actor_user_id: int | None,
    actor_label: str,
    event_type: str,
    details: dict[str, object] | None = None,
) -> None:
    session.add(
        WorkspaceEvent(
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            actor_label=actor_label,
            event_type=event_type,
            details=json.dumps(details or {}, sort_keys=True),
        )
    )


def _management_access(
    session: Session,
    authenticated: AuthenticatedUser,
    workspace_id: int,
    *,
    allow_closed_owner: bool = False,
) -> tuple[Workspace, WorkspaceMembership]:
    bind_account(session, authenticated.id)
    membership = session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == authenticated.id,
        )
    )
    workspace = session.get(Workspace, workspace_id) if membership is not None else None
    if membership is None or workspace is None:
        raise PermissionError("Workspace not found")
    if membership.role not in {OWNER_ROLE, ADMIN_ROLE}:
        raise PermissionError("This workspace role cannot manage people")
    if workspace.status != ACTIVE_WORKSPACE and not (
        allow_closed_owner and membership.role == OWNER_ROLE
    ):
        raise PermissionError("This workspace is closed")
    bind_workspace(
        session,
        WorkspaceAccess(
            user_id=authenticated.id,
            actor_label=authenticated.display_name,
            workspace_id=workspace.id,
            role=membership.role,
            linked_consultant_id=membership.linked_consultant_id,
        ),
    )
    return workspace, membership


def list_managed_workspaces(
    session: Session, authenticated: AuthenticatedUser
) -> tuple[WorkspaceListItem, ...]:
    bind_account(session, authenticated.id)
    rows = session.execute(
        select(Workspace, WorkspaceMembership)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(
            WorkspaceMembership.user_id == authenticated.id,
            WorkspaceMembership.role.in_((OWNER_ROLE, ADMIN_ROLE)),
            or_(
                Workspace.status == ACTIVE_WORKSPACE,
                and_(
                    Workspace.status == CLOSED_WORKSPACE,
                    WorkspaceMembership.role == OWNER_ROLE,
                ),
            ),
        )
        .order_by(Workspace.status, Workspace.name, Workspace.id)
    )
    return tuple(
        WorkspaceListItem(
            id=workspace.id,
            name=workspace.name,
            role=membership.role,
            status=workspace.status,
            closed_at=workspace.closed_at,
            purge_after=workspace.purge_after,
        )
        for workspace, membership in rows
    )


def workspace_details(
    session: Session, authenticated: AuthenticatedUser, workspace_id: int
) -> WorkspaceDetails:
    workspace, current = _management_access(
        session, authenticated, workspace_id, allow_closed_owner=True
    )
    people_rows = session.execute(
        select(WorkspaceMembership, User, Consultant.name)
        .join(User, User.id == WorkspaceMembership.user_id)
        .outerjoin(
            Consultant,
            (Consultant.workspace_id == WorkspaceMembership.workspace_id)
            & (Consultant.id == WorkspaceMembership.linked_consultant_id),
        )
        .where(WorkspaceMembership.workspace_id == workspace_id)
        .order_by(WorkspaceMembership.role.desc(), User.display_name, User.id)
    )
    people = tuple(
        WorkspacePerson(
            membership_id=membership.id,
            user_id=user.id,
            public_id=user.public_id,
            display_name=user.display_name,
            display_email=user.display_email,
            role=membership.role,
            linked_consultant_id=membership.linked_consultant_id,
            linked_consultant_name=consultant_name,
        )
        for membership, user, consultant_name in people_rows
    )
    invitation_rows = session.scalars(
        select(WorkspaceInvitation)
        .where(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.status == PENDING_INVITATION,
        )
        .order_by(WorkspaceInvitation.created_at.desc())
    )
    invitations = tuple(
        WorkspaceInvitationItem(
            id=invitation.id,
            display_email=invitation.display_email,
            role=invitation.role,
            linked_consultant_id=invitation.linked_consultant_id,
            status=invitation.status,
            expires_at=invitation.expires_at,
        )
        for invitation in invitation_rows
    )
    consultants = tuple(
        (consultant_id, name)
        for consultant_id, name in session.execute(
            select(Consultant.id, Consultant.name)
            .where(
                Consultant.workspace_id == workspace_id,
                Consultant.archived_at.is_(None),
            )
            .order_by(Consultant.name, Consultant.id)
        )
    )
    transfer_row = session.execute(
        select(WorkspaceOwnershipTransfer, User.display_name)
        .join(User, User.id == WorkspaceOwnershipTransfer.to_user_id)
        .where(
            WorkspaceOwnershipTransfer.workspace_id == workspace_id,
            WorkspaceOwnershipTransfer.status == PENDING_TRANSFER,
        )
    ).one_or_none()
    transfer = (
        WorkspaceTransferItem(
            id=transfer_row[0].id,
            from_user_id=transfer_row[0].from_user_id,
            to_user_id=transfer_row[0].to_user_id,
            to_display_name=transfer_row[1],
            expires_at=transfer_row[0].expires_at,
            can_accept=transfer_row[0].to_user_id == authenticated.id,
        )
        if transfer_row is not None
        else None
    )
    event_rows = session.scalars(
        select(WorkspaceEvent)
        .where(WorkspaceEvent.workspace_id == workspace_id)
        .order_by(WorkspaceEvent.recorded_at.desc(), WorkspaceEvent.id.desc())
        .limit(30)
    )
    events = tuple(
        WorkspaceEventItem(
            id=event.id,
            actor_label=event.actor_label,
            event_type=event.event_type,
            details=json.loads(event.details),
            recorded_at=event.recorded_at,
        )
        for event in event_rows
    )
    return WorkspaceDetails(
        workspace=workspace,
        current_role=current.role,
        people=people,
        invitations=invitations,
        consultants=consultants,
        transfer=transfer,
        events=events,
    )


def rename_workspace(
    session: Session,
    authenticated: AuthenticatedUser,
    workspace_id: int,
    name: str,
) -> WorkspaceDetails:
    workspace, membership = _management_access(session, authenticated, workspace_id)
    if membership.role != OWNER_ROLE:
        raise PermissionError("Only the Owner can rename this workspace")
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Enter a workspace name")
    old_name = workspace.name
    workspace.name = cleaned
    _record_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=authenticated.id,
        actor_label=authenticated.display_name,
        event_type="workspace_renamed",
        details={"from": old_name, "to": cleaned},
    )
    session.flush()
    return workspace_details(session, authenticated, workspace_id)


def create_invitation(
    session: Session,
    authenticated: AuthenticatedUser,
    workspace_id: int,
    *,
    email: str,
    role: str,
    linked_consultant_id: int | None,
) -> tuple[WorkspaceInvitation, str, str]:
    workspace, current = _management_access(session, authenticated, workspace_id)
    if role not in {ADMIN_ROLE, MEMBER_ROLE}:
        raise ValueError("Choose Admin or Member")
    if current.role == ADMIN_ROLE and role != MEMBER_ROLE:
        raise PermissionError("Admins can only invite Members")
    if role == MEMBER_ROLE and linked_consultant_id is None:
        raise ValueError("Choose the consultant this Member can view")
    if role == ADMIN_ROLE:
        linked_consultant_id = None
    if linked_consultant_id is not None:
        consultant_exists = session.scalar(
            select(Consultant.id).where(
                Consultant.workspace_id == workspace_id,
                Consultant.id == linked_consultant_id,
                Consultant.archived_at.is_(None),
            )
        )
        if consultant_exists is None:
            raise ValueError("Choose an active consultant in this workspace")

    identity = normalise_email(email)
    existing_user = session.scalar(select(User).where(User.canonical_email == identity.canonical))
    existing_membership = (
        session.scalar(
            select(WorkspaceMembership.id).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == existing_user.id,
            )
        )
        if existing_user is not None
        else None
    )
    if existing_membership is not None:
        raise ValueError("That account already belongs to this workspace")
    existing_invitation = session.scalar(
        select(WorkspaceInvitation).where(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.canonical_email == identity.canonical,
            WorkspaceInvitation.status == PENDING_INVITATION,
        )
    )
    if existing_invitation is not None:
        raise ValueError("A pending invitation already exists for this address")

    issued = issue_action(
        session,
        purpose=INVITATION,
        canonical_email=identity.canonical,
        display_email=identity.display,
        lifetime=INVITATION_LIFETIME,
        user_id=None,
        workspace_id=workspace_id,
    )
    invitation = WorkspaceInvitation(
        workspace_id=workspace_id,
        canonical_email=identity.canonical,
        display_email=identity.display,
        role=role,
        linked_consultant_id=linked_consultant_id,
        invited_by_user_id=authenticated.id,
        action_token_id=issued.record.id,
        status=PENDING_INVITATION,
        created_at=issued.record.created_at,
        expires_at=issued.record.expires_at,
    )
    session.add(invitation)
    _record_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=authenticated.id,
        actor_label=authenticated.display_name,
        event_type="invitation_created",
        details={"email": identity.display, "role": role},
    )
    session.flush()
    return invitation, issued.raw_token, workspace.name


def resend_invitation(
    session: Session,
    authenticated: AuthenticatedUser,
    workspace_id: int,
    invitation_id: int,
) -> tuple[WorkspaceInvitation, str, str]:
    workspace, current = _management_access(session, authenticated, workspace_id)
    invitation = session.scalar(
        select(WorkspaceInvitation)
        .where(
            WorkspaceInvitation.id == invitation_id,
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.status == PENDING_INVITATION,
        )
        .with_for_update()
    )
    if invitation is None:
        raise LookupError("Invitation not found")
    if current.role == ADMIN_ROLE and invitation.role != MEMBER_ROLE:
        raise PermissionError("Admins can only manage Member invitations")
    issued = issue_action(
        session,
        purpose=INVITATION,
        canonical_email=invitation.canonical_email,
        display_email=invitation.display_email,
        lifetime=INVITATION_LIFETIME,
        user_id=None,
        workspace_id=workspace_id,
    )
    invitation.action_token_id = issued.record.id
    invitation.claimed_by_user_id = None
    invitation.created_at = issued.record.created_at
    invitation.expires_at = issued.record.expires_at
    _record_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=authenticated.id,
        actor_label=authenticated.display_name,
        event_type="invitation_resent",
        details={"email": invitation.display_email},
    )
    session.flush()
    return invitation, issued.raw_token, workspace.name


def revoke_invitation(
    session: Session,
    authenticated: AuthenticatedUser,
    workspace_id: int,
    invitation_id: int,
) -> None:
    _workspace, current = _management_access(session, authenticated, workspace_id)
    invitation = session.scalar(
        select(WorkspaceInvitation)
        .where(
            WorkspaceInvitation.id == invitation_id,
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.status == PENDING_INVITATION,
        )
        .with_for_update()
    )
    if invitation is None:
        raise LookupError("Invitation not found")
    if current.role == ADMIN_ROLE and invitation.role != MEMBER_ROLE:
        raise PermissionError("Admins can only manage Member invitations")
    moment = _now()
    invitation.status = REVOKED_INVITATION
    invitation.revoked_at = moment
    if invitation.action_token_id is not None:
        token = session.get(AccountActionToken, invitation.action_token_id)
        if token is not None and token.consumed_at is None:
            token.revoked_at = moment
    _record_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=authenticated.id,
        actor_label=authenticated.display_name,
        event_type="invitation_revoked",
        details={"email": invitation.display_email},
    )


def _accept_invitation_record(
    session: Session, invitation: WorkspaceInvitation, account: User, *, moment: datetime
) -> None:
    if membership_for_user(session, account.id, invitation.workspace_id) is None:
        session.add(
            WorkspaceMembership(
                workspace_id=invitation.workspace_id,
                user_id=account.id,
                role=invitation.role,
                linked_consultant_id=invitation.linked_consultant_id,
            )
        )
    invitation.status = ACCEPTED_INVITATION
    invitation.accepted_at = moment
    invitation.claimed_by_user_id = account.id
    _record_event(
        session,
        workspace_id=invitation.workspace_id,
        actor_user_id=account.id,
        actor_label=account.display_name,
        event_type="invitation_accepted",
        details={"role": invitation.role},
    )


def accept_invitation(session: Session, authenticated: AuthenticatedUser, raw_token: str) -> int:
    account = session.get(User, authenticated.id)
    action = valid_action(session, purpose=INVITATION, raw_token=raw_token)
    if account is None or action is None or action.workspace_id is None:
        raise ValueError("This invitation is invalid, expired, or has already been used")
    if account.canonical_email != action.canonical_email:
        raise PermissionError("Sign in with the email address this invitation was sent to")
    bind_workspace(
        session,
        WorkspaceAccess(
            user_id=account.id,
            actor_label=account.display_name,
            workspace_id=action.workspace_id,
            role=MEMBER_ROLE,
        ),
    )
    invitation = session.scalar(
        select(WorkspaceInvitation).where(
            WorkspaceInvitation.action_token_id == action.id,
            WorkspaceInvitation.status == PENDING_INVITATION,
        )
    )
    workspace = session.get(Workspace, action.workspace_id)
    if invitation is None or workspace is None or workspace.status != ACTIVE_WORKSPACE:
        raise ValueError("This invitation is invalid, expired, or has already been used")
    use_current_workspace_revision(session, workspace)
    moment = _now()
    consume_action(action, now=moment)
    _accept_invitation_record(session, invitation, account, moment=moment)
    session.flush()
    return invitation.workspace_id


def claim_invitation_for_registration(session: Session, *, raw_token: str, account: User) -> None:
    action = valid_action(session, purpose=INVITATION, raw_token=raw_token)
    if (
        action is None
        or action.workspace_id is None
        or account.canonical_email != action.canonical_email
    ):
        raise ValueError("This invitation is invalid or was sent to a different email address")
    bind_workspace(
        session,
        WorkspaceAccess(
            user_id=account.id,
            actor_label=account.display_name,
            workspace_id=action.workspace_id,
            role=MEMBER_ROLE,
        ),
    )
    invitation = session.scalar(
        select(WorkspaceInvitation).where(
            WorkspaceInvitation.action_token_id == action.id,
            WorkspaceInvitation.status == PENDING_INVITATION,
        )
    )
    if invitation is None:
        raise ValueError("This invitation is invalid, expired, or has already been used")
    consume_action(action)
    invitation.claimed_by_user_id = account.id


def accept_claimed_invitations(session: Session, account: User) -> None:
    invitations = tuple(
        session.scalars(
            select(WorkspaceInvitation).where(
                WorkspaceInvitation.claimed_by_user_id == account.id,
                WorkspaceInvitation.status == PENDING_INVITATION,
            )
        )
    )
    moment = _now()
    for invitation in invitations:
        workspace = session.get(Workspace, invitation.workspace_id)
        if workspace is not None and workspace.status == ACTIVE_WORKSPACE:
            use_current_workspace_revision(session, workspace)
            bind_workspace(
                session,
                WorkspaceAccess(
                    user_id=account.id,
                    actor_label=account.display_name,
                    workspace_id=invitation.workspace_id,
                    role=invitation.role,
                    linked_consultant_id=invitation.linked_consultant_id,
                ),
            )
            _accept_invitation_record(session, invitation, account, moment=moment)
            session.flush()


def update_member(
    session: Session,
    authenticated: AuthenticatedUser,
    workspace_id: int,
    membership_id: int,
    *,
    role: str,
    linked_consultant_id: int | None,
) -> None:
    _workspace, current = _management_access(session, authenticated, workspace_id)
    target = session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.id == membership_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
    )
    if target is None:
        raise LookupError("Member not found")
    if target.role == OWNER_ROLE:
        raise PermissionError("Ownership must be transferred explicitly")
    if current.role == ADMIN_ROLE and (target.role != MEMBER_ROLE or role != MEMBER_ROLE):
        raise PermissionError("Admins can only update Members")
    if role not in {ADMIN_ROLE, MEMBER_ROLE}:
        raise ValueError("Choose Admin or Member")
    if role == MEMBER_ROLE and linked_consultant_id is None:
        raise ValueError("Choose the consultant this Member can view")
    if role == ADMIN_ROLE:
        linked_consultant_id = None
    elif (
        session.scalar(
            select(Consultant.id).where(
                Consultant.workspace_id == workspace_id,
                Consultant.id == linked_consultant_id,
                Consultant.archived_at.is_(None),
            )
        )
        is None
    ):
        raise ValueError("Choose an active consultant in this workspace")
    target.role = role
    target.linked_consultant_id = linked_consultant_id
    _record_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=authenticated.id,
        actor_label=authenticated.display_name,
        event_type="member_updated",
        details={"membership_id": target.id, "role": role},
    )


def remove_member(
    session: Session,
    authenticated: AuthenticatedUser,
    workspace_id: int,
    membership_id: int,
) -> None:
    _workspace, current = _management_access(session, authenticated, workspace_id)
    target = session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.id == membership_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
    )
    if target is None:
        raise LookupError("Member not found")
    if target.role == OWNER_ROLE:
        raise PermissionError("The Owner cannot be removed")
    if current.role == ADMIN_ROLE and target.role != MEMBER_ROLE:
        raise PermissionError("Admins can only remove Members")
    user_id = target.user_id
    session.delete(target)
    session.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.active_workspace_id == workspace_id)
        .values(active_workspace_id=None)
    )
    session.execute(
        update(User)
        .where(User.id == user_id, User.last_workspace_id == workspace_id)
        .values(last_workspace_id=None)
    )
    _record_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=authenticated.id,
        actor_label=authenticated.display_name,
        event_type="member_removed",
        details={"user_id": user_id},
    )


def initiate_ownership_transfer(
    session: Session,
    authenticated: AuthenticatedUser,
    workspace_id: int,
    target_membership_id: int,
) -> None:
    _workspace, current = _management_access(session, authenticated, workspace_id)
    if current.role != OWNER_ROLE:
        raise PermissionError("Only the Owner can transfer ownership")
    target = session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.id == target_membership_id,
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.role == ADMIN_ROLE,
        )
    )
    if target is None:
        raise ValueError("Choose an Admin to receive ownership")
    existing = session.scalar(
        select(WorkspaceOwnershipTransfer).where(
            WorkspaceOwnershipTransfer.workspace_id == workspace_id,
            WorkspaceOwnershipTransfer.status == PENDING_TRANSFER,
        )
    )
    if existing is not None:
        existing.status = CANCELLED_TRANSFER
        existing.completed_at = _now()
    moment = _now()
    session.add(
        WorkspaceOwnershipTransfer(
            workspace_id=workspace_id,
            from_user_id=authenticated.id,
            to_user_id=target.user_id,
            status=PENDING_TRANSFER,
            created_at=moment,
            expires_at=moment + TRANSFER_LIFETIME,
        )
    )
    _record_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=authenticated.id,
        actor_label=authenticated.display_name,
        event_type="ownership_transfer_requested",
        details={"to_user_id": target.user_id},
    )


def accept_ownership_transfer(
    session: Session,
    authenticated: AuthenticatedUser,
    workspace_id: int,
    transfer_id: int,
) -> None:
    _workspace, current = _management_access(session, authenticated, workspace_id)
    transfer = session.scalar(
        select(WorkspaceOwnershipTransfer)
        .where(
            WorkspaceOwnershipTransfer.id == transfer_id,
            WorkspaceOwnershipTransfer.workspace_id == workspace_id,
            WorkspaceOwnershipTransfer.status == PENDING_TRANSFER,
        )
        .with_for_update()
    )
    if (
        transfer is None
        or transfer.to_user_id != authenticated.id
        or current.role != ADMIN_ROLE
        or _comparable(transfer.expires_at) <= _now()
    ):
        raise PermissionError("This ownership transfer cannot be accepted")
    session.execute(
        update(WorkspaceMembership)
        .where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == transfer.from_user_id,
            WorkspaceMembership.role == OWNER_ROLE,
        )
        .values(role=ADMIN_ROLE)
    )
    session.execute(
        update(WorkspaceMembership)
        .where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == transfer.to_user_id,
            WorkspaceMembership.role == ADMIN_ROLE,
        )
        .values(role=OWNER_ROLE)
    )
    transfer.status = ACCEPTED_TRANSFER
    transfer.completed_at = _now()
    _record_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=authenticated.id,
        actor_label=authenticated.display_name,
        event_type="ownership_transferred",
        details={"from_user_id": transfer.from_user_id, "to_user_id": transfer.to_user_id},
    )


def workspace_impact(
    session: Session, authenticated: AuthenticatedUser, workspace_id: int
) -> WorkspaceImpact:
    _management_access(session, authenticated, workspace_id, allow_closed_owner=True)
    consultants = int(
        session.scalar(
            select(func.count())
            .select_from(Consultant)
            .where(Consultant.workspace_id == workspace_id)
        )
        or 0
    )
    corrections = int(
        session.scalar(
            select(func.count())
            .select_from(HolidayCorrectionRecord)
            .where(HolidayCorrectionRecord.workspace_id == workspace_id)
        )
        or 0
    )
    from audit import AuditEvent

    audit_events = int(
        session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.workspace_id == workspace_id)
        )
        or 0
    )
    pending = int(
        session.scalar(
            select(func.count())
            .select_from(WorkspaceInvitation)
            .where(
                WorkspaceInvitation.workspace_id == workspace_id,
                WorkspaceInvitation.status == PENDING_INVITATION,
            )
        )
        or 0
    )
    history = consultants > 0 or corrections > 0 or audit_events > 0
    return WorkspaceImpact(
        consultants=consultants,
        pending_invitations=pending,
        has_operational_history=history,
        can_delete_immediately=not history,
    )


def delete_empty_workspace(
    session: Session,
    authenticated: AuthenticatedUser,
    workspace_id: int,
    confirmation_name: str,
) -> None:
    workspace, current = _management_access(session, authenticated, workspace_id)
    if current.role != OWNER_ROLE:
        raise PermissionError("Only the Owner can delete this workspace")
    impact = workspace_impact(session, authenticated, workspace_id)
    if not impact.can_delete_immediately:
        raise ValueError("A workspace with operational history must be closed instead")
    if confirmation_name != workspace.name:
        raise ValueError("Type the workspace name exactly to confirm deletion")
    session.execute(
        update(UserSession)
        .where(UserSession.active_workspace_id == workspace_id)
        .values(active_workspace_id=None)
    )
    session.execute(
        update(User).where(User.last_workspace_id == workspace_id).values(last_workspace_id=None)
    )
    session.delete(workspace)


def close_workspace(
    session: Session, authenticated: AuthenticatedUser, workspace_id: int, confirmation_name: str
) -> None:
    workspace, current = _management_access(session, authenticated, workspace_id)
    if current.role != OWNER_ROLE:
        raise PermissionError("Only the Owner can close this workspace")
    if confirmation_name != workspace.name:
        raise ValueError("Type the workspace name exactly to confirm closure")
    moment = _now()
    purge_after = moment + WORKSPACE_RECOVERY_LIFETIME
    workspace.status = CLOSED_WORKSPACE
    workspace.closed_at = moment
    workspace.purge_after = purge_after
    invitation_ids = select(WorkspaceInvitation.action_token_id).where(
        WorkspaceInvitation.workspace_id == workspace_id,
        WorkspaceInvitation.status == PENDING_INVITATION,
        WorkspaceInvitation.action_token_id.is_not(None),
    )
    session.execute(
        update(AccountActionToken)
        .where(AccountActionToken.id.in_(invitation_ids))
        .values(revoked_at=moment)
    )
    session.execute(
        update(WorkspaceInvitation)
        .where(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.status == PENDING_INVITATION,
        )
        .values(status=REVOKED_INVITATION, revoked_at=moment)
    )
    session.execute(
        update(WorkspaceOwnershipTransfer)
        .where(
            WorkspaceOwnershipTransfer.workspace_id == workspace_id,
            WorkspaceOwnershipTransfer.status == PENDING_TRANSFER,
        )
        .values(status=CANCELLED_TRANSFER, completed_at=moment)
    )
    session.execute(
        update(UserSession)
        .where(UserSession.active_workspace_id == workspace_id)
        .values(active_workspace_id=None)
    )
    session.execute(
        update(User).where(User.last_workspace_id == workspace_id).values(last_workspace_id=None)
    )
    _record_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=authenticated.id,
        actor_label=authenticated.display_name,
        event_type="workspace_closed",
        details={"recover_until": purge_after.isoformat()},
    )


def recover_workspace(
    session: Session, authenticated: AuthenticatedUser, workspace_id: int
) -> None:
    workspace, current = _management_access(
        session, authenticated, workspace_id, allow_closed_owner=True
    )
    if current.role != OWNER_ROLE or workspace.status != CLOSED_WORKSPACE:
        raise PermissionError("Only the Owner can recover a closed workspace")
    if workspace.purge_after is None or _comparable(workspace.purge_after) <= _now():
        raise ValueError("The workspace recovery period has ended")
    workspace.status = ACTIVE_WORKSPACE
    workspace.closed_at = None
    workspace.purge_after = None
    _record_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=authenticated.id,
        actor_label=authenticated.display_name,
        event_type="workspace_recovered",
    )


def purge_closed_workspace(
    session: Session,
    *,
    workspace_id: int,
    confirmation_name: str,
    now: datetime | None = None,
) -> str:
    """Permanently remove one closed workspace after its recovery deadline."""

    workspace = session.get(Workspace, workspace_id)
    if workspace is None or workspace.status != CLOSED_WORKSPACE:
        raise ValueError("Choose a closed workspace")
    moment = _comparable(now or _now())
    if workspace.purge_after is None or _comparable(workspace.purge_after) > moment:
        raise ValueError("The workspace recovery period has not ended")
    if confirmation_name != workspace.name:
        raise ValueError("Type the workspace name exactly to confirm permanent deletion")

    from audit import AuditEvent

    removed_name = workspace.name
    session.execute(delete(AuditEvent).where(AuditEvent.workspace_id == workspace_id))
    session.execute(delete(Consultant).where(Consultant.workspace_id == workspace_id))
    session.execute(
        delete(HolidayCorrectionRecord).where(HolidayCorrectionRecord.workspace_id == workspace_id)
    )
    session.delete(workspace)
    return removed_name


__all__ = [
    "WorkspaceDetails",
    "WorkspaceImpact",
    "accept_claimed_invitations",
    "accept_invitation",
    "accept_ownership_transfer",
    "claim_invitation_for_registration",
    "close_workspace",
    "create_invitation",
    "delete_empty_workspace",
    "initiate_ownership_transfer",
    "list_managed_workspaces",
    "purge_closed_workspace",
    "recover_workspace",
    "remove_member",
    "rename_workspace",
    "resend_invitation",
    "revoke_invitation",
    "update_member",
    "workspace_details",
    "workspace_impact",
]
