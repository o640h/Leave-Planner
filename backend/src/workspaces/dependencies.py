"""FastAPI authorization dependencies for workspace-scoped requests."""

from fastapi import Request, Response
from sqlalchemy import select

from authentication.dependencies import require_authenticated_request, runtime_settings
from dependencies import DatabaseSession
from errors import ApiError

from .models import ADMIN_ROLE, INITIAL_WORKSPACE_ID, MEMBER_ROLE, OWNER_ROLE, Workspace
from .service import WorkspaceAccess, bind_workspace, membership_for_user


def require_workspace_request(
    request: Request, response: Response, session: DatabaseSession
) -> WorkspaceAccess:
    """Require any current workspace membership without granting planner write authority."""

    authenticated = require_authenticated_request(request, response, session)
    if not runtime_settings(request).authentication_required:
        access = WorkspaceAccess(
            user_id=authenticated.id,
            actor_label=authenticated.display_name,
            workspace_id=INITIAL_WORKSPACE_ID,
            role=ADMIN_ROLE,
        )
        bind_workspace(session, access)
        return access

    if authenticated.active_workspace_id is None:
        raise ApiError(
            status_code=403,
            code="workspace_selection_required",
            message="Select a workspace to continue",
        )

    membership = membership_for_user(session, authenticated.id, authenticated.active_workspace_id)
    if membership is None:
        raise ApiError(
            status_code=403,
            code="workspace_access_denied",
            message="This account does not have access to the selected workspace",
        )

    access = WorkspaceAccess(
        user_id=authenticated.id,
        actor_label=authenticated.display_name,
        workspace_id=membership.workspace_id,
        role=membership.role,
        linked_consultant_id=membership.linked_consultant_id,
    )
    bind_workspace(session, access)
    revision = session.scalar(
        select(Workspace.revision).where(Workspace.id == membership.workspace_id)
    )
    if revision is not None:
        response.headers["X-Workspace-Revision"] = str(revision)
    return access


def require_operator_workspace_request(
    request: Request, response: Response, session: DatabaseSession
) -> WorkspaceAccess:
    access = require_workspace_request(request, response, session)
    if access.role not in {OWNER_ROLE, ADMIN_ROLE}:
        raise ApiError(
            status_code=403,
            code="workspace_role_denied",
            message="This workspace role cannot use the operator planner",
        )
    return access


def require_member_workspace_request(
    request: Request, response: Response, session: DatabaseSession
) -> WorkspaceAccess:
    """Require the restricted Member surface for the selected workspace."""

    access = require_workspace_request(request, response, session)
    if access.role != MEMBER_ROLE:
        raise ApiError(
            status_code=403,
            code="workspace_role_denied",
            message="This workspace role cannot use the Member workspace",
        )
    return access
