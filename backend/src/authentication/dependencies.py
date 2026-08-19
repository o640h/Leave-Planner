"""FastAPI authentication and CSRF enforcement."""

from fastapi import Request
from sqlalchemy.orm import Session

from dependencies import DatabaseSession
from errors import ApiError
from settings import Settings

from .service import AuthenticatedUser, authenticated_user, csrf_is_valid

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def runtime_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def current_user(request: Request, session: Session) -> AuthenticatedUser | None:
    settings = runtime_settings(request)
    if not settings.authentication_required:
        return AuthenticatedUser(id=0, display_name="Test Operator", session_id=0)
    return authenticated_user(session, request.cookies.get(settings.session_cookie_name))


def validate_request_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is None:
        return
    expected = str(request.base_url).rstrip("/")
    if origin.rstrip("/") != expected:
        raise ApiError(status_code=403, code="csrf_failed", message="Request could not be verified")


def require_authenticated_request(request: Request, session: DatabaseSession) -> AuthenticatedUser:
    authenticated = current_user(request, session)
    if authenticated is None:
        raise ApiError(
            status_code=401,
            code="authentication_required",
            message="Sign in to continue",
        )

    settings = runtime_settings(request)
    if settings.authentication_required and request.method in UNSAFE_METHODS:
        validate_request_origin(request)
        csrf_header = request.headers.get("X-CSRF-Token")
        csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
        if not csrf_header or not csrf_cookie or not secrets_match(csrf_header, csrf_cookie):
            raise ApiError(
                status_code=403,
                code="csrf_failed",
                message="Request could not be verified",
            )
        if not csrf_is_valid(session, authenticated.session_id, csrf_header):
            raise ApiError(
                status_code=403,
                code="csrf_failed",
                message="Request could not be verified",
            )
    return authenticated


def secrets_match(first: str, second: str) -> bool:
    import secrets

    return secrets.compare_digest(first, second)
