"""FastAPI authorization dependency for the private team workspace."""

from fastapi import Request

from authentication.dependencies import require_authenticated_request, runtime_settings
from dependencies import DatabaseSession
from errors import ApiError

from .models import ADMIN_ROLE, INITIAL_WORKSPACE_ID
from .service import WorkspaceAccess, bind_workspace, membership_for_user


def require_workspace_request(request: Request, session: DatabaseSession) -> WorkspaceAccess:
    authenticated = require_authenticated_request(request, session)
    if not runtime_settings(request).authentication_required:
        access = WorkspaceAccess(
            user_id=authenticated.id,
            actor_label=authenticated.display_name,
            workspace_id=INITIAL_WORKSPACE_ID,
            role=ADMIN_ROLE,
        )
        bind_workspace(session, access)
        return access

    membership = membership_for_user(session, authenticated.id)
    if membership is None or membership.role != ADMIN_ROLE:
        raise ApiError(
            status_code=403,
            code="workspace_access_denied",
            message="This account does not have access to the workspace",
        )

    access = WorkspaceAccess(
        user_id=authenticated.id,
        actor_label=authenticated.display_name,
        workspace_id=membership.workspace_id,
        role=membership.role,
    )
    bind_workspace(session, access)
    return access
