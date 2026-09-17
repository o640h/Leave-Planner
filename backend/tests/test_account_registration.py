"""Explicit account registration and empty workspace creation acceptance tests."""

from pathlib import Path
from typing import cast
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select

from authentication.models import ACTIVE, PENDING_VERIFICATION, User
from consultants.models import Consultant
from database import create_database_engine, create_session_factory, session_scope
from main import create_app
from migrations import upgrade_database
from settings import RegistrationMode, Settings
from workspaces.models import OWNER_ROLE, WorkspaceMembership

ORIGIN = "http://testserver"
EMAIL = "new-owner@example.org"
PASSWORD = "account-password"


def application(
    tmp_path: Path, *, mode: RegistrationMode, limit: int = 3
) -> tuple[FastAPI, Settings]:
    settings = Settings(
        environment="test",
        data_dir=tmp_path,
        public_origin=ORIGIN,
        registration_mode=mode,
        owned_workspace_limit=limit,
    )
    upgrade_database(settings.resolved_database_url)
    return create_app(settings=settings, frontend_dist=tmp_path / "missing"), settings


def verification_token(message: str) -> str:
    link = next(word for word in message.split() if "?action=" in word)
    return parse_qs(urlparse(link).query)["token"][0]


def test_registration_modes_fail_closed(tmp_path: Path) -> None:
    for mode in ("closed", "invitation_only"):
        app, _settings = application(tmp_path / mode, mode=mode)
        with TestClient(app) as client:
            assert client.get("/api/auth/registration").json() == {"mode": mode}
            response = client.post(
                "/api/auth/registration",
                headers={"Origin": ORIGIN},
                json={"display_name": "New Owner", "email": EMAIL, "password": PASSWORD},
            )
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "registration_unavailable"


def test_open_registration_is_available_in_production() -> None:
    settings = Settings(
        environment="production",
        database_url=SecretStr("postgresql+psycopg://leave_planner:secret@database/leave_planner"),
        public_origin="https://app.merydio.co.uk",
        registration_mode="open",
    )
    assert settings.registration_mode == "open"


def test_verified_account_explicitly_creates_empty_workspaces_up_to_the_limit(
    tmp_path: Path,
) -> None:
    app, settings = application(tmp_path, mode="open", limit=2)
    with TestClient(app) as client:
        registered = client.post(
            "/api/auth/registration",
            headers={"Origin": ORIGIN},
            json={"display_name": "New Owner", "email": EMAIL, "password": PASSWORD},
        )
        assert registered.status_code == 200
        assert registered.json()["message"] == (
            "Check your email for the next account-creation step."
        )
        messages = cast(
            list[dict[str, str]], client.get("/api/auth/development/email-outbox").json()
        )
        token = verification_token(messages[-1]["text"])
        wrong_password_repeat = client.post(
            "/api/auth/registration",
            headers={"Origin": ORIGIN},
            json={"display_name": "Different Name", "email": EMAIL, "password": "different8"},
        )
        assert wrong_password_repeat.status_code == 200
        assert wrong_password_repeat.json() == registered.json()
        assert len(client.get("/api/auth/development/email-outbox").json()) == 1

        engine = create_database_engine(settings.resolved_database_url)
        try:
            with session_scope(create_session_factory(engine)) as session:
                account = session.scalar(select(User).where(User.canonical_email == EMAIL))
                assert account is not None
                assert account.security_state == PENDING_VERIFICATION
                assert session.scalar(select(func.count()).select_from(WorkspaceMembership)) == 0
        finally:
            engine.dispose()

        confirmed = client.post(
            "/api/auth/verification/confirm",
            headers={"Origin": ORIGIN},
            json={"token": token},
        )
        assert confirmed.status_code == 200
        active_repeat = client.post(
            "/api/auth/registration",
            headers={"Origin": ORIGIN},
            json={"display_name": "Different Name", "email": EMAIL, "password": PASSWORD},
        )
        assert active_repeat.status_code == 409
        assert active_repeat.json()["error"] == {
            "code": "account_already_registered",
            "message": "An account with this email address is already registered.",
            "details": None,
        }
        assert len(client.get("/api/auth/development/email-outbox").json()) == 1
        signed_in = client.post(
            "/api/auth/login",
            headers={"Origin": ORIGIN},
            json={"email": EMAIL, "password": PASSWORD},
        )
        assert signed_in.status_code == 200
        assert signed_in.json()["workspace"]["state"] == "onboarding"
        csrf = client.cookies.get("leave_planner_csrf")
        assert csrf
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}

        first = client.post("/api/workspaces", headers=headers, json={"name": "First Practice"})
        assert first.status_code == 200
        assert first.json()["state"] == "active"
        assert first.json()["memberships"][0]["role"] == OWNER_ROLE
        second = client.post("/api/workspaces", headers=headers, json={"name": "Second Practice"})
        assert second.status_code == 200
        assert second.json()["active_workspace_id"] != first.json()["active_workspace_id"]
        blocked = client.post("/api/workspaces", headers=headers, json={"name": "Third Practice"})
        assert blocked.status_code == 409
        assert blocked.json()["error"]["code"] == "workspace_creation_unavailable"

        engine = create_database_engine(settings.resolved_database_url)
        try:
            with session_scope(create_session_factory(engine)) as session:
                account = session.scalar(select(User).where(User.canonical_email == EMAIL))
                assert account is not None
                assert account.security_state == ACTIVE
                memberships = tuple(
                    session.scalars(
                        select(WorkspaceMembership).where(WorkspaceMembership.user_id == account.id)
                    )
                )
                assert len(memberships) == 2
                assert {membership.role for membership in memberships} == {OWNER_ROLE}
                assert session.scalar(select(func.count()).select_from(Consultant)) == 0
        finally:
            engine.dispose()
