"""Workspace selection API contracts."""

from typing import Literal

from pydantic import BaseModel

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
