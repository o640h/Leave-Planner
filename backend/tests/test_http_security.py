"""Hosted origin, request-boundary, and browser-header tests."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from http_security import HostedHttpSecurityMiddleware
from main import create_app
from settings import Settings

DATABASE_URL = SecretStr(
    "postgresql+psycopg://leave_planner:secret@database/leave_planner"
)
PUBLIC_ORIGIN = "https://leaveplanner.synology.me"


def production_settings(
    *,
    max_request_bytes: int = 1_048_576,
    request_rate_limit: int = 240,
    login_rate_limit: int = 10,
) -> Settings:
    return Settings(
        environment="production",
        database_url=DATABASE_URL,
        public_origin=PUBLIC_ORIGIN,
        max_request_bytes=max_request_bytes,
        request_rate_limit=request_rate_limit,
        login_rate_limit=login_rate_limit,
    )


def boundary_app(settings: Settings) -> FastAPI:
    app = FastAPI()
    app.add_middleware(HostedHttpSecurityMiddleware, settings=settings)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[settings.public_host or ""],
    )

    @app.post("/echo-size")
    async def echo_size(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    @app.get("/probe")
    async def probe() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_production_requires_an_exact_https_public_origin() -> None:
    with pytest.raises(RuntimeError, match="PUBLIC_ORIGIN"):
        create_app(settings=Settings(environment="production", database_url=DATABASE_URL))

    with pytest.raises(ValidationError, match="must use HTTPS"):
        Settings(
            environment="production",
            database_url=DATABASE_URL,
            public_origin="http://leaveplanner.synology.me",
        )

    with pytest.raises(ValidationError, match="without a path"):
        Settings(
            environment="production",
            database_url=DATABASE_URL,
            public_origin=f"{PUBLIC_ORIGIN}/unexpected",
        )


def test_hosted_boundary_preserves_body_and_rejects_oversized_requests() -> None:
    settings = production_settings(max_request_bytes=16)
    with TestClient(boundary_app(settings), base_url=PUBLIC_ORIGIN) as client:
        accepted = client.post("/echo-size", content=b"1234567890")
        rejected = client.post("/echo-size", content=b"12345678901234567")

    assert accepted.json() == {"size": 10}
    assert rejected.status_code == 413
    assert rejected.json()["error"]["code"] == "request_too_large"
    assert rejected.headers["X-Content-Type-Options"] == "nosniff"


def test_hosted_boundary_limits_clients_and_rejects_unknown_hosts() -> None:
    settings = production_settings(request_rate_limit=2)
    app = boundary_app(settings)
    with TestClient(app, base_url=PUBLIC_ORIGIN) as client:
        assert client.get("/probe").status_code == 200
        second = client.get("/probe")
        limited = client.get("/probe")
        wrong_host = client.get("/probe", headers={"Host": "attacker.example"})

    assert second.headers["Strict-Transport-Security"] == "max-age=31536000"
    assert second.headers["Content-Security-Policy"].startswith("default-src 'self'")
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0
    assert wrong_host.status_code == 400


def test_login_has_a_stricter_per_client_limit() -> None:
    settings = production_settings(request_rate_limit=20, login_rate_limit=1)
    app = boundary_app(settings)

    @app.post("/api/auth/login")
    async def login_probe() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app, base_url=PUBLIC_ORIGIN) as client:
        assert client.post("/api/auth/login", json={"password": "example"}).status_code == 200
        limited = client.post("/api/auth/login", json={"password": "example"})

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limit_exceeded"
