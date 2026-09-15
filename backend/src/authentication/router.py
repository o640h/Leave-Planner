"""Email-and-password login, current-session, and logout endpoints."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from dependencies import DatabaseSession
from errors import ApiError
from settings import Settings
from workspaces.schemas import context_read
from workspaces.service import initial_workspace_id, workspace_context

from .dependencies import (
    current_user,
    require_authenticated_request,
    runtime_settings,
    validate_request_origin,
)
from .schemas import AuthenticatedUserRead, LoginRequest, SessionRead
from .service import (
    AuthenticatedUser,
    account_for_email,
    clear_failed_logins,
    create_session,
    lockout_remaining_seconds,
    password_is_valid,
    record_failed_login,
    record_security_event,
    revoke_session,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
INVALID_CREDENTIALS = "Sign in could not be completed. Check your details and try again."


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def set_authentication_cookies(
    response: Response, settings: Settings, session_token: str, csrf_token: str
) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        session_token,
        secure=settings.secure_cookies,
        httponly=True,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        secure=settings.secure_cookies,
        httponly=False,
        samesite="strict",
        path="/",
    )


def clear_authentication_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.secure_cookies)
    response.delete_cookie(settings.csrf_cookie_name, path="/", secure=settings.secure_cookies)


def user_read(authenticated: AuthenticatedUser) -> AuthenticatedUserRead:
    return AuthenticatedUserRead(
        public_id=authenticated.public_id,
        display_name=authenticated.display_name,
        display_email=authenticated.display_email,
    )


def session_read(session: DatabaseSession, authenticated: AuthenticatedUser) -> SessionRead:
    return SessionRead(
        authenticated=True,
        user=user_read(authenticated),
        workspace=context_read(
            workspace_context(session, authenticated.id, authenticated.active_workspace_id)
        ),
    )


@router.get("/session", response_model=SessionRead)
def session_status(request: Request, response: Response, session: DatabaseSession) -> SessionRead:
    no_store(response)
    authenticated = current_user(request, session)
    if authenticated is None:
        return SessionRead(authenticated=False)
    return session_read(session, authenticated)


@router.post("/login", response_model=SessionRead)
def login(
    details: LoginRequest,
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> SessionRead:
    settings = runtime_settings(request)
    validate_request_origin(request)
    user = account_for_email(session, str(details.email), for_update=True)
    locked = user is not None and lockout_remaining_seconds(user) > 0
    valid = password_is_valid(user, details.password)

    if locked or not valid:
        if user is not None and not locked:
            record_failed_login(user)
        record_security_event(
            session,
            "login_failed",
            user_id=user.id if user else None,
            actor_label=user.display_name if user else "Unknown Account",
            details={"source": "http"},
        )
        session.commit()
        raise ApiError(status_code=401, code="invalid_credentials", message=INVALID_CREDENTIALS)

    assert user is not None
    clear_failed_logins(user)
    active_workspace_id = initial_workspace_id(session, user)
    tokens = create_session(
        session,
        user,
        lifetime=timedelta(hours=settings.session_lifetime_hours),
        active_workspace_id=active_workspace_id,
    )
    set_authentication_cookies(response, settings, tokens.session_token, tokens.csrf_token)
    no_store(response)
    authenticated = AuthenticatedUser(
        id=user.id,
        public_id=user.public_id,
        display_name=user.display_name,
        display_email=user.display_email,
        session_id=tokens.session_id,
        active_workspace_id=tokens.active_workspace_id,
    )
    return session_read(session, authenticated)


@router.post("/logout", response_model=SessionRead)
def logout(
    request: Request,
    response: Response,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> SessionRead:
    revoke_session(session, authenticated)
    clear_authentication_cookies(response, runtime_settings(request))
    no_store(response)
    return SessionRead(authenticated=False)
