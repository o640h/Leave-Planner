"""Authenticated active-workspace selection endpoints."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request

from authentication.account_actions import (
    INVITATION,
    action_link,
    deliver_message,
    invitation_message,
)
from authentication.dependencies import require_authenticated_request, runtime_settings
from authentication.email_delivery import EmailSender
from authentication.schemas import MessageRead
from authentication.service import (
    AuthenticatedUser,
    reauthenticate_session,
    record_security_event,
)
from dependencies import DatabaseSession
from errors import ApiError

from .management import (
    accept_invitation,
    accept_ownership_transfer,
    close_workspace,
    create_invitation,
    delete_empty_workspace,
    initiate_ownership_transfer,
    list_managed_workspaces,
    recover_workspace,
    remove_member,
    rename_workspace,
    resend_invitation,
    revoke_invitation,
    update_member,
    workspace_details,
    workspace_impact,
)
from .schemas import (
    InvitationAcceptanceRequest,
    OwnershipTransferRequest,
    WorkspaceConfirmationRequest,
    WorkspaceContextRead,
    WorkspaceCreateRequest,
    WorkspaceDetailsRead,
    WorkspaceImpactRead,
    WorkspaceInvitationRequest,
    WorkspaceListItemRead,
    WorkspaceMemberUpdateRequest,
    WorkspaceRenameRequest,
    WorkspaceSelectionRequest,
    context_read,
    details_read,
    impact_read,
    workspace_list_read,
)
from .service import create_owned_workspace, select_workspace, workspace_context

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


def _management_error(error: Exception) -> ApiError:
    if isinstance(error, PermissionError):
        return ApiError(status_code=403, code="workspace_management_denied", message=str(error))
    if isinstance(error, LookupError):
        return ApiError(status_code=404, code="workspace_record_not_found", message=str(error))
    return ApiError(status_code=409, code="workspace_management_conflict", message=str(error))


def _deliver_invitation(
    request: Request,
    session: DatabaseSession,
    *,
    invitation_id: int,
    token_id: int,
    recipient: str,
    workspace_name: str,
    role: str,
    raw_token: str,
    authenticated: AuthenticatedUser,
) -> None:
    origin = runtime_settings(request).public_origin or str(request.base_url).rstrip("/")
    link = action_link(origin, "accept-invitation", raw_token)
    attempt = deliver_message(
        session,
        cast(EmailSender, request.app.state.email_sender),
        purpose=INVITATION,
        message=invitation_message(recipient, workspace_name, role, link),
        action_token_id=token_id,
    )
    record_security_event(
        session,
        (
            "invitation_delivery_succeeded"
            if attempt.status == "sent"
            else "invitation_delivery_failed"
        ),
        user_id=authenticated.id,
        actor_label=authenticated.display_name,
        details={"invitation_id": invitation_id, "failure_code": attempt.failure_code},
    )
    session.commit()


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


@router.get("/managed", response_model=list[WorkspaceListItemRead])
def managed_workspaces(
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> list[WorkspaceListItemRead]:
    return [workspace_list_read(item) for item in list_managed_workspaces(session, authenticated)]


@router.post("/invitations/accept", response_model=WorkspaceContextRead)
def accept_workspace_invitation(
    details: InvitationAcceptanceRequest,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> WorkspaceContextRead:
    try:
        workspace_id = accept_invitation(session, authenticated, details.token)
        membership = select_workspace(
            session,
            user_id=authenticated.id,
            user_session_id=authenticated.session_id,
            workspace_id=workspace_id,
        )
        if membership is None:
            raise RuntimeError("The accepted workspace could not be selected")
        session.commit()
    except (ValueError, PermissionError) as error:
        raise _management_error(error) from error
    return context_read(workspace_context(session, authenticated.id, workspace_id))


@router.get("/{workspace_id}/management", response_model=WorkspaceDetailsRead)
def read_workspace_management(
    workspace_id: int,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> WorkspaceDetailsRead:
    try:
        return details_read(workspace_details(session, authenticated, workspace_id))
    except PermissionError as error:
        raise _management_error(error) from error


@router.put("/{workspace_id}/management", response_model=WorkspaceDetailsRead)
def update_workspace_name(
    workspace_id: int,
    details: WorkspaceRenameRequest,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> WorkspaceDetailsRead:
    try:
        result = rename_workspace(session, authenticated, workspace_id, details.name)
        session.commit()
        return details_read(result)
    except (ValueError, PermissionError) as error:
        raise _management_error(error) from error


@router.post("/{workspace_id}/invitations", response_model=WorkspaceDetailsRead)
def invite_workspace_person(
    workspace_id: int,
    details: WorkspaceInvitationRequest,
    request: Request,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> WorkspaceDetailsRead:
    try:
        invitation, raw_token, workspace_name = create_invitation(
            session,
            authenticated,
            workspace_id,
            email=str(details.email),
            role=details.role,
            linked_consultant_id=details.linked_consultant_id,
        )
        session.commit()
        assert invitation.action_token_id is not None
        _deliver_invitation(
            request,
            session,
            invitation_id=invitation.id,
            token_id=invitation.action_token_id,
            recipient=invitation.display_email,
            workspace_name=workspace_name,
            role=invitation.role,
            raw_token=raw_token,
            authenticated=authenticated,
        )
        return details_read(workspace_details(session, authenticated, workspace_id))
    except (ValueError, PermissionError) as error:
        raise _management_error(error) from error


@router.post(
    "/{workspace_id}/invitations/{invitation_id}/resend",
    response_model=WorkspaceDetailsRead,
)
def resend_workspace_invitation(
    workspace_id: int,
    invitation_id: int,
    request: Request,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> WorkspaceDetailsRead:
    try:
        invitation, raw_token, workspace_name = resend_invitation(
            session, authenticated, workspace_id, invitation_id
        )
        session.commit()
        assert invitation.action_token_id is not None
        _deliver_invitation(
            request,
            session,
            invitation_id=invitation.id,
            token_id=invitation.action_token_id,
            recipient=invitation.display_email,
            workspace_name=workspace_name,
            role=invitation.role,
            raw_token=raw_token,
            authenticated=authenticated,
        )
        return details_read(workspace_details(session, authenticated, workspace_id))
    except (LookupError, PermissionError) as error:
        raise _management_error(error) from error


@router.delete("/{workspace_id}/invitations/{invitation_id}", response_model=WorkspaceDetailsRead)
def revoke_workspace_invitation(
    workspace_id: int,
    invitation_id: int,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> WorkspaceDetailsRead:
    try:
        revoke_invitation(session, authenticated, workspace_id, invitation_id)
        session.commit()
        return details_read(workspace_details(session, authenticated, workspace_id))
    except (LookupError, PermissionError) as error:
        raise _management_error(error) from error


@router.patch("/{workspace_id}/members/{membership_id}", response_model=WorkspaceDetailsRead)
def change_workspace_member(
    workspace_id: int,
    membership_id: int,
    details: WorkspaceMemberUpdateRequest,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> WorkspaceDetailsRead:
    try:
        update_member(
            session,
            authenticated,
            workspace_id,
            membership_id,
            role=details.role,
            linked_consultant_id=details.linked_consultant_id,
        )
        session.commit()
        return details_read(workspace_details(session, authenticated, workspace_id))
    except (ValueError, LookupError, PermissionError) as error:
        raise _management_error(error) from error


@router.delete("/{workspace_id}/members/{membership_id}", response_model=WorkspaceDetailsRead)
def delete_workspace_member(
    workspace_id: int,
    membership_id: int,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> WorkspaceDetailsRead:
    try:
        remove_member(session, authenticated, workspace_id, membership_id)
        session.commit()
        return details_read(workspace_details(session, authenticated, workspace_id))
    except (LookupError, PermissionError) as error:
        raise _management_error(error) from error


@router.post("/{workspace_id}/ownership-transfers", response_model=WorkspaceDetailsRead)
def request_workspace_ownership_transfer(
    workspace_id: int,
    details: OwnershipTransferRequest,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> WorkspaceDetailsRead:
    try:
        initiate_ownership_transfer(
            session, authenticated, workspace_id, details.target_membership_id
        )
        session.commit()
        return details_read(workspace_details(session, authenticated, workspace_id))
    except (ValueError, PermissionError) as error:
        raise _management_error(error) from error


@router.post(
    "/{workspace_id}/ownership-transfers/{transfer_id}/accept",
    response_model=WorkspaceDetailsRead,
)
def confirm_workspace_ownership_transfer(
    workspace_id: int,
    transfer_id: int,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> WorkspaceDetailsRead:
    try:
        accept_ownership_transfer(session, authenticated, workspace_id, transfer_id)
        session.commit()
        return details_read(workspace_details(session, authenticated, workspace_id))
    except PermissionError as error:
        raise _management_error(error) from error


@router.get("/{workspace_id}/impact", response_model=WorkspaceImpactRead)
def read_workspace_impact(
    workspace_id: int,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> WorkspaceImpactRead:
    try:
        return impact_read(workspace_impact(session, authenticated, workspace_id))
    except PermissionError as error:
        raise _management_error(error) from error


@router.delete("/{workspace_id}", response_model=WorkspaceContextRead)
def delete_workspace(
    workspace_id: int,
    details: WorkspaceConfirmationRequest,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> WorkspaceContextRead:
    try:
        delete_empty_workspace(session, authenticated, workspace_id, details.confirmation_name)
        session.commit()
        return context_read(workspace_context(session, authenticated.id, None))
    except (ValueError, PermissionError) as error:
        raise _management_error(error) from error


@router.post("/{workspace_id}/close", response_model=WorkspaceContextRead)
def close_managed_workspace(
    workspace_id: int,
    details: WorkspaceConfirmationRequest,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> WorkspaceContextRead:
    if details.password is None or not reauthenticate_session(
        session, authenticated, details.password
    ):
        raise ApiError(
            status_code=401,
            code="reauthentication_failed",
            message="Your password could not be confirmed.",
        )
    try:
        close_workspace(session, authenticated, workspace_id, details.confirmation_name)
        session.commit()
        return context_read(workspace_context(session, authenticated.id, None))
    except (ValueError, PermissionError) as error:
        raise _management_error(error) from error


@router.post("/{workspace_id}/recover", response_model=MessageRead)
def recover_managed_workspace(
    workspace_id: int,
    details: WorkspaceConfirmationRequest,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> MessageRead:
    if details.password is None or not reauthenticate_session(
        session, authenticated, details.password
    ):
        raise ApiError(
            status_code=401,
            code="reauthentication_failed",
            message="Your password could not be confirmed.",
        )
    try:
        recover_workspace(session, authenticated, workspace_id)
        session.commit()
        return MessageRead(message="Workspace recovered.")
    except (ValueError, PermissionError) as error:
        raise _management_error(error) from error
