"""Persisted private workspaces and their authorized users."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
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


class Workspace(Base):
    """One private team data boundary."""

    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
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
