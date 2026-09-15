"""Hosted HTTP boundary limits and browser security headers."""

from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from time import monotonic

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from settings import Settings

CallNext = Callable[[Request], Awaitable[Response]]


class HostedHttpSecurityMiddleware(BaseHTTPMiddleware):
    """Reject oversized or excessive requests and harden hosted responses."""

    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.logins: dict[str, deque[float]] = defaultdict(deque)
        self.account_actions: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                return self.secure_response(
                    self.error_response(400, "invalid_request", "Request could not be read")
                )
            if declared_size < 0:
                return self.secure_response(
                    self.error_response(400, "invalid_request", "Request could not be read")
                )
            if declared_size > self.settings.max_request_bytes:
                return self.secure_response(
                    self.error_response(
                        413, "request_too_large", "Request exceeds the permitted size"
                    )
                )

        if request.method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            if len(body) > self.settings.max_request_bytes:
                return self.secure_response(
                    self.error_response(
                        413, "request_too_large", "Request exceeds the permitted size"
                    )
                )

        client = request.client.host if request.client is not None else "unknown"
        retry_after = self.retry_after(
            self.requests[client], limit=self.settings.request_rate_limit
        )
        if retry_after:
            return self.secure_response(self.rate_limited_response(retry_after))

        if request.url.path == "/api/auth/login" and request.method == "POST":
            retry_after = self.retry_after(
                self.logins[client], limit=self.settings.login_rate_limit
            )
            if retry_after:
                return self.secure_response(self.rate_limited_response(retry_after))

        account_action_paths = {
            "/api/auth/verification/confirm",
            "/api/auth/password-reset/request",
            "/api/auth/password-reset/confirm",
            "/api/auth/email-change/request",
            "/api/auth/email-change/confirm",
        }
        if request.url.path in account_action_paths and request.method == "POST":
            retry_after = self.retry_after(
                self.account_actions[client], limit=self.settings.account_action_rate_limit
            )
            if retry_after:
                return self.secure_response(self.rate_limited_response(retry_after))

        response = await call_next(request)
        return self.secure_response(response)

    def secure_response(self, response: Response) -> Response:
        if self.settings.environment == "production":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; base-uri 'self'; form-action 'self'; "
                "frame-ancestors 'none'; object-src 'none'; "
                "script-src 'self'; style-src 'self'; font-src 'self'; "
                "img-src 'self' data:; connect-src 'self'"
            )
            response.headers["Permissions-Policy"] = (
                "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
            )
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
        return response

    def retry_after(self, attempts: deque[float], *, limit: int) -> int:
        now = monotonic()
        cutoff = now - self.settings.rate_limit_window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if len(attempts) >= limit:
            remaining = self.settings.rate_limit_window_seconds - (now - attempts[0])
            return max(1, int(remaining + 0.999))
        attempts.append(now)
        return 0

    @staticmethod
    def error_response(status_code: int, code: str, message: str) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={"error": {"code": code, "message": message, "details": None}},
        )

    @classmethod
    def rate_limited_response(cls, retry_after: int) -> JSONResponse:
        response = cls.error_response(
            429,
            "rate_limit_exceeded",
            "Too many requests. Please wait and try again.",
        )
        response.headers["Retry-After"] = str(retry_after)
        return response
