"""Hosted HTTP boundary limits, trusted client identity, and browser headers."""

from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import Awaitable, Callable
from ipaddress import ip_address
from threading import Lock
from time import monotonic

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from settings import Settings

CallNext = Callable[[Request], Awaitable[Response]]


class SlidingWindowLimiter:
    """Thread-safe, bounded sliding-window counters for HTTP and WebSockets."""

    def __init__(self, *, window_seconds: int, max_keys: int) -> None:
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._attempts: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def retry_after(self, key: str, *, limit: int) -> int:
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            attempts = self._attempts.pop(key, deque())
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            if len(attempts) >= limit:
                self._attempts[key] = attempts
                return max(1, int(self.window_seconds - (now - attempts[0]) + 0.999))
            attempts.append(now)
            self._attempts[key] = attempts
            while len(self._attempts) > self.max_keys:
                self._attempts.popitem(last=False)
        return 0


class SecurityRateLimits:
    """Application-owned rate limiters shared by HTTP and WebSocket boundaries."""

    def __init__(self, settings: Settings) -> None:
        arguments = {
            "window_seconds": settings.rate_limit_window_seconds,
            "max_keys": settings.rate_limit_max_keys,
        }
        self.requests = SlidingWindowLimiter(**arguments)
        self.logins = SlidingWindowLimiter(**arguments)
        self.account_actions = SlidingWindowLimiter(**arguments)
        self.sensitive_actions = SlidingWindowLimiter(**arguments)
        self.websocket_connections = SlidingWindowLimiter(**arguments)


def client_key(
    *, peer_host: str | None,
    cloudflare_connecting_ip: str | None,
    settings: Settings,
) -> str | None:
    """Resolve a rate-limit key without trusting caller-controlled forwarding headers."""
    candidate = peer_host
    if settings.trusted_proxy_mode == "cloudflare_tunnel":
        try:
            peer_address = ip_address(peer_host) if peer_host is not None else None
            if peer_address is None or peer_address.is_loopback or not peer_address.is_private:
                return None
        except ValueError:
            # ASGI test clients use an opaque peer name. A deployed Uvicorn peer is an IP.
            pass
        candidate = cloudflare_connecting_ip
    if candidate is None:
        return None
    candidate = candidate.strip()
    try:
        return ip_address(candidate).compressed
    except ValueError:
        return candidate if settings.trusted_proxy_mode == "none" and candidate else None


def enforce_account_action_limit(request: Request, user_id: int, action: str) -> None:
    """Apply an authenticated per-account limit to a sensitive mutation."""
    retry_after = account_action_retry_after(request, user_id, action)
    if retry_after:
        from errors import ApiError

        raise ApiError(
            status_code=429,
            code="rate_limit_exceeded",
            message="Too many requests. Please wait and try again.",
            headers={"Retry-After": str(retry_after)},
        )


def account_action_retry_after(request: Request, user_id: int, action: str) -> int:
    """Return a per-account delay when a caller needs an enumeration-safe response."""
    limits: SecurityRateLimits = request.app.state.security_rate_limits
    settings: Settings = request.app.state.settings
    return limits.sensitive_actions.retry_after(
        f"{action}:{user_id}", limit=settings.sensitive_action_rate_limit
    )


class HostedHttpSecurityMiddleware(BaseHTTPMiddleware):
    """Reject oversized or excessive requests and harden hosted responses."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        settings: Settings,
        limits: SecurityRateLimits | None = None,
    ) -> None:
        super().__init__(app)
        self.settings = settings
        self.limits = limits or SecurityRateLimits(settings)

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

        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            body = await request.body()
            if len(body) > self.settings.max_request_bytes:
                return self.secure_response(
                    self.error_response(
                        413, "request_too_large", "Request exceeds the permitted size"
                    )
                )

        peer = request.client.host if request.client is not None else None
        client = client_key(
            peer_host=peer,
            cloudflare_connecting_ip=request.headers.get("cf-connecting-ip"),
            settings=self.settings,
        )
        if client is None and request.url.path != "/api/health":
            return self.secure_response(
                self.error_response(400, "invalid_client_address", "Request could not be read")
            )
        client = client or "health-check"

        retry_after = self.limits.requests.retry_after(
            client, limit=self.settings.request_rate_limit
        )
        if retry_after:
            return self.secure_response(self.rate_limited_response(retry_after))

        if request.url.path == "/api/auth/login" and request.method == "POST":
            retry_after = self.limits.logins.retry_after(
                client, limit=self.settings.login_rate_limit
            )
            if retry_after:
                return self.secure_response(self.rate_limited_response(retry_after))

        account_action_paths = {
            "/api/auth/verification/confirm",
            "/api/auth/password-reset/request",
            "/api/auth/password-reset/confirm",
            "/api/auth/email-change/request",
            "/api/auth/email-change/confirm",
            "/api/auth/registration",
        }
        if request.url.path in account_action_paths and request.method == "POST":
            retry_after = self.limits.account_actions.retry_after(
                client, limit=self.settings.account_action_rate_limit
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
                "script-src 'self'; style-src 'self'; style-src-elem 'self'; "
                "style-src-attr 'unsafe-inline'; font-src 'self'; "
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
