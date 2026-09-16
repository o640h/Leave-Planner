"""Persisted private workspaces and their authorized users."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

INITIAL_WORKSPACE_ID = 1
INITIAL_WORKSPACE_NAME = "Leave Planner"
OWNER_ROLE = "owner"
ADMIN_ROLE = "admin"
MEMBER_ROLE = "member"
WORKSPACE_ROLES = (OWNER_ROLE, ADMIN_ROLE, MEMBER_ROLE)
ACTIVE_WORKSPACE = "active"
CLOSED_WORKSPACE = "closed"
PENDING_INVITATION = "pending"
ACCEPTED_INVITATION = "accepted"
REVOKED_INVITATION = "revoked"
PENDING_TRANSFER = "pending"
ACCEPTED_TRANSFER = "accepted"
CANCELLED_TRANSFER = "cancelled"


class Workspace(Base):
    """One private team data boundary."""

    __tablename__ = "workspaces"

    __table_args__ = (
        CheckConstraint("status IN ('active', 'closed')", name="ck_workspaces_status"),
        CheckConstraint(
            "(status = 'active' AND closed_at IS NULL AND purge_after IS NULL) OR "
            "(status = 'closed' AND closed_at IS NOT NULL AND purge_after IS NOT NULL)",
            name="ck_workspaces_lifecycle",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ACTIVE_WORKSPACE)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purge_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False
    )


class WorkspaceMembership(Base):
    """An application user authorized for one workspace."""

    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership"),
        ForeignKeyConstraint(
            ("workspace_id", "linked_consultant_id"),
            ("consultants.workspace_id", "consultants.id"),
            name="fk_workspace_membership_linked_consultant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "role IN ('owner', 'admin', 'member')",
            name="ck_workspace_membership_role",
        ),
        CheckConstraint(
            "role = 'member' OR linked_consultant_id IS NULL",
            name="ck_workspace_membership_consultant_role",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False, default=ADMIN_ROLE)
    linked_consultant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False
    )


class WorkspaceInvitation(Base):
    """One revocable invitation to a workspace role."""

    __tablename__ = "workspace_invitations"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'member')", name="ck_workspace_invitation_role"),
        CheckConstraint(
            "role = 'member' OR linked_consultant_id IS NULL",
            name="ck_workspace_invitation_consultant_role",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'revoked')",
            name="ck_workspace_invitation_status",
        ),
        ForeignKeyConstraint(
            ("workspace_id", "linked_consultant_id"),
            ("consultants.workspace_id", "consultants.id"),
            name="fk_workspace_invitation_linked_consultant",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    canonical_email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    linked_consultant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    invited_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    claimed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action_token_id: Mapped[int | None] = mapped_column(
        ForeignKey("account_action_tokens.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PENDING_INVITATION)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkspaceOwnershipTransfer(Base):
    """An Owner-initiated transfer awaiting the target Admin's acceptance."""

    __tablename__ = "workspace_ownership_transfers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'cancelled')",
            name="ck_workspace_ownership_transfer_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PENDING_TRANSFER)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkspaceEvent(Base):
    """A workspace-level history entry for membership and lifecycle administration."""

    __tablename__ = "workspace_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_label: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False, index=True
    )
