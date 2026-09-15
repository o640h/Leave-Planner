"""Authenticated active-workspace selection endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from authentication.dependencies import require_authenticated_request
from authentication.service import AuthenticatedUser
from dependencies import DatabaseSession
from errors import ApiError

from .schemas import WorkspaceContextRead, WorkspaceSelectionRequest, context_read
from .service import select_workspace, workspace_context

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post("/active", response_model=WorkspaceContextRead)
def update_active_workspace(
    details: WorkspaceSelectionRequest,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> WorkspaceContextRead:
    membership = select_workspace(
        session,
        user_id=authenticated.id,
        user_session_id=authenticated.session_id,
        workspace_id=details.workspace_id,
    )
    if membership is None:
        raise ApiError(
            status_code=404,
            code="workspace_not_found",
            message="The workspace could not be selected",
        )
    return context_read(workspace_context(session, authenticated.id, membership.workspace_id))
