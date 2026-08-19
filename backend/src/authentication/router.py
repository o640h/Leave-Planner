"""Password-only login, current-session, and logout endpoints."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from dependencies import DatabaseSession
from errors import ApiError
from settings import Settings

from .dependencies import (
    current_user,
    require_authenticated_request,
    runtime_settings,
    validate_request_origin,
)
from .schemas import AuthenticatedUserRead, LoginRequest, SessionRead
from .service import (
    AuthenticatedUser,
    admin_user,
    clear_failed_logins,
    create_session,
    lockout_remaining_seconds,
    password_is_valid,
    record_failed_login,
    record_security_event,
    revoke_session,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


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


@router.get("/session", response_model=SessionRead)
def session_status(request: Request, response: Response, session: DatabaseSession) -> SessionRead:
    no_store(response)
    authenticated = current_user(request, session)
    if authenticated is None:
        return SessionRead(authenticated=False)
    return SessionRead(
        authenticated=True,
        user=AuthenticatedUserRead(id=authenticated.id, display_name=authenticated.display_name),
    )


@router.post("/login", response_model=SessionRead)
def login(
    details: LoginRequest,
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> SessionRead:
    settings = runtime_settings(request)
    validate_request_origin(request)
    user = admin_user(session, for_update=True)
    retry_after = lockout_remaining_seconds(user) if user else 0
    if retry_after:
        assert user is not None
        password_is_valid(user, details.password)
        record_security_event(
            session,
            "login_blocked",
            user_id=user.id,
            actor_label="Admin",
            details={"source": "http"},
        )
        session.commit()
        raise ApiError(
            status_code=429,
            code="login_unavailable",
            message="Sign in could not be completed. Please wait and try again.",
            details={"retry_after_seconds": retry_after},
        )

    if not password_is_valid(user, details.password):
        locked_for = record_failed_login(user) if user else 0
        record_security_event(
            session,
            "login_locked" if locked_for else "login_failed",
            user_id=user.id if user else None,
            actor_label="Admin",
            details={"source": "http"},
        )
        session.commit()
        if locked_for:
            raise ApiError(
                status_code=429,
                code="login_unavailable",
                message="Sign in could not be completed. Please wait and try again.",
                details={"retry_after_seconds": locked_for},
            )
        raise ApiError(
            status_code=401,
            code="invalid_credentials",
            message="Sign in could not be completed. Check the password and try again.",
        )

    assert user is not None
    clear_failed_logins(user)
    tokens = create_session(
        session,
        user,
        lifetime=timedelta(hours=settings.session_lifetime_hours),
    )
    set_authentication_cookies(response, settings, tokens.session_token, tokens.csrf_token)
    no_store(response)
    return SessionRead(
        authenticated=True,
        user=AuthenticatedUserRead(id=user.id, display_name=user.display_name),
    )


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
