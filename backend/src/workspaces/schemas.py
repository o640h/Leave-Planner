"""Workspace selection API contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from .management import WorkspaceDetails, WorkspaceImpact, WorkspaceListItem
from .service import WorkspaceContext


class WorkspaceMembershipRead(BaseModel):
    workspace_id: int
    workspace_name: str
    role: Literal["owner", "admin", "member"]
    linked_consultant_id: int | None


class WorkspaceContextRead(BaseModel):
    state: Literal["active", "selection_required", "onboarding"]
    active_workspace_id: int | None
    memberships: list[WorkspaceMembershipRead]


class WorkspaceSelectionRequest(BaseModel):
    workspace_id: int


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class WorkspaceRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class WorkspaceListItemRead(BaseModel):
    workspace_id: int
    workspace_name: str
    role: Literal["owner", "admin"]
    status: Literal["active", "closed"]
    closed_at: datetime | None
    purge_after: datetime | None


class WorkspacePersonRead(BaseModel):
    membership_id: int
    user_id: int
    public_id: str
    display_name: str
    display_email: str
    role: Literal["owner", "admin", "member"]
    linked_consultant_id: int | None
    linked_consultant_name: str | None


class WorkspaceInvitationRead(BaseModel):
    invitation_id: int
    display_email: str
    role: Literal["admin", "member"]
    linked_consultant_id: int | None
    status: Literal["pending"]
    expires_at: datetime


class WorkspaceConsultantRead(BaseModel):
    consultant_id: int
    name: str


class WorkspaceTransferRead(BaseModel):
    transfer_id: int
    from_user_id: int
    to_user_id: int
    to_display_name: str
    expires_at: datetime
    can_accept: bool


class WorkspaceEventRead(BaseModel):
    event_id: int
    actor_label: str
    event_type: str
    details: dict[str, object]
    recorded_at: datetime


class WorkspaceDetailsRead(BaseModel):
    workspace_id: int
    workspace_name: str
    status: Literal["active", "closed"]
    closed_at: datetime | None
    purge_after: datetime | None
    current_role: Literal["owner", "admin"]
    people: list[WorkspacePersonRead]
    invitations: list[WorkspaceInvitationRead]
    consultants: list[WorkspaceConsultantRead]
    transfer: WorkspaceTransferRead | None
    recent_events: list[WorkspaceEventRead]


class WorkspaceInvitationRequest(BaseModel):
    email: EmailStr
    role: Literal["admin", "member"]
    linked_consultant_id: int | None = None


class InvitationAcceptanceRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)


class WorkspaceMemberUpdateRequest(BaseModel):
    role: Literal["admin", "member"]
    linked_consultant_id: int | None = None


class OwnershipTransferRequest(BaseModel):
    target_membership_id: int


class WorkspaceConfirmationRequest(BaseModel):
    confirmation_name: str = Field(min_length=1, max_length=160)
    password: str | None = Field(default=None, min_length=1, max_length=1024)


class WorkspaceImpactRead(BaseModel):
    consultants: int
    pending_invitations: int
    has_operational_history: bool
    can_delete_immediately: bool


def context_read(context: WorkspaceContext) -> WorkspaceContextRead:
    return WorkspaceContextRead(
        state=context.state,  # type: ignore[arg-type]
        active_workspace_id=context.active_workspace_id,
        memberships=[
            WorkspaceMembershipRead(
                workspace_id=membership.id,
                workspace_name=membership.name,
                role=membership.role,  # type: ignore[arg-type]
                linked_consultant_id=membership.linked_consultant_id,
            )
            for membership in context.memberships
        ],
    )


def workspace_list_read(item: WorkspaceListItem) -> WorkspaceListItemRead:
    return WorkspaceListItemRead(
        workspace_id=item.id,
        workspace_name=item.name,
        role=item.role,  # type: ignore[arg-type]
        status=item.status,  # type: ignore[arg-type]
        closed_at=item.closed_at,
        purge_after=item.purge_after,
    )


def details_read(details: WorkspaceDetails) -> WorkspaceDetailsRead:
    return WorkspaceDetailsRead(
        workspace_id=details.workspace.id,
        workspace_name=details.workspace.name,
        status=details.workspace.status,  # type: ignore[arg-type]
        closed_at=details.workspace.closed_at,
        purge_after=details.workspace.purge_after,
        current_role=details.current_role,  # type: ignore[arg-type]
        people=[
            WorkspacePersonRead(
                membership_id=person.membership_id,
                user_id=person.user_id,
                public_id=person.public_id,
                display_name=person.display_name,
                display_email=person.display_email,
                role=person.role,  # type: ignore[arg-type]
                linked_consultant_id=person.linked_consultant_id,
                linked_consultant_name=person.linked_consultant_name,
            )
            for person in details.people
        ],
        invitations=[
            WorkspaceInvitationRead(
                invitation_id=invitation.id,
                display_email=invitation.display_email,
                role=invitation.role,  # type: ignore[arg-type]
                linked_consultant_id=invitation.linked_consultant_id,
                status="pending",
                expires_at=invitation.expires_at,
            )
            for invitation in details.invitations
        ],
        consultants=[
            WorkspaceConsultantRead(consultant_id=consultant_id, name=name)
            for consultant_id, name in details.consultants
        ],
        transfer=(
            WorkspaceTransferRead(
                transfer_id=details.transfer.id,
                from_user_id=details.transfer.from_user_id,
                to_user_id=details.transfer.to_user_id,
                to_display_name=details.transfer.to_display_name,
                expires_at=details.transfer.expires_at,
                can_accept=details.transfer.can_accept,
            )
            if details.transfer is not None
            else None
        ),
        recent_events=[
            WorkspaceEventRead(
                event_id=event.id,
                actor_label=event.actor_label,
                event_type=event.event_type,
                details=event.details,
                recorded_at=event.recorded_at,
            )
            for event in details.events
        ],
    )


def impact_read(impact: WorkspaceImpact) -> WorkspaceImpactRead:
    return WorkspaceImpactRead(
        consultants=impact.consultants,
        pending_invitations=impact.pending_invitations,
        has_operational_history=impact.has_operational_history,
        can_delete_immediately=impact.can_delete_immediately,
    )
