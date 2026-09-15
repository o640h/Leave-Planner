"""Authenticated active-workspace selection endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from authentication.dependencies import require_authenticated_request, runtime_settings
from authentication.service import AuthenticatedUser
from dependencies import DatabaseSession
from errors import ApiError

from .schemas import (
    WorkspaceContextRead,
    WorkspaceCreateRequest,
    WorkspaceSelectionRequest,
    context_read,
)
from .service import create_owned_workspace, select_workspace, workspace_context

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceContextRead)
def create_workspace(
    details: WorkspaceCreateRequest,
    request: Request,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> WorkspaceContextRead:
    try:
        context = create_owned_workspace(
            session,
            user_id=authenticated.id,
            user_session_id=authenticated.session_id,
            workspace_name=details.name,
            owned_workspace_limit=runtime_settings(request).owned_workspace_limit,
        )
    except ValueError as error:
        raise ApiError(
            status_code=409,
            code="workspace_creation_unavailable",
            message=str(error),
        ) from error
    return context_read(context)


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
