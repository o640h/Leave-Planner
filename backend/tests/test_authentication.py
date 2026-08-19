"""Authentication, session, CSRF, and account-administration integration tests."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import select

from authentication import admin as admin_command
from authentication.models import SecurityEvent, UserSession
from authentication.passwords import MINIMUM_PASSWORD_LENGTH
from authentication.router import set_authentication_cookies
from authentication.service import (
    admin_user,
    authenticated_user,
    create_admin,
    create_session,
    lockout_remaining_seconds,
    record_failed_login,
    reset_admin_password,
    set_admin_enabled,
)
from database import create_database_engine, create_session_factory, session_scope
from main import create_app
from migrations import upgrade_database
from settings import Settings
from workspaces.models import WorkspaceMembership

PASSWORD = "shared-admin-password"
NEW_PASSWORD = "replacement-password"


def configured_app(data_dir: Path) -> tuple[FastAPI, Settings]:
    settings = Settings(environment="test", data_dir=data_dir)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            create_admin(session, PASSWORD)
    finally:
        engine.dispose()
    return create_app(settings=settings, frontend_dist=data_dir / "missing-frontend"), settings


def csrf_headers(client: TestClient, *, origin: str = "http://testserver") -> dict[str, str]:
    token = client.cookies.get("leave_planner_csrf")
    assert token
    return {"X-CSRF-Token": token, "Origin": origin}


def test_login_protects_application_apis_and_logout_revokes_session(tmp_path: Path) -> None:
    app, settings = configured_app(tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/consultants").status_code == 401
        assert client.get("/api/auth/session").json() == {
            "authenticated": False,
            "user": None,
        }

        rejected = client.post("/api/auth/login", json={"password": "incorrect-password"})
        assert rejected.status_code == 401
        assert rejected.json()["error"]["code"] == "invalid_credentials"
        assert rejected.headers["Cache-Control"] == "no-store"

        cross_origin_login = client.post(
            "/api/auth/login",
            json={"password": PASSWORD},
            headers={"Origin": "https://attacker.example"},
        )
        assert cross_origin_login.status_code == 403

        accepted = client.post("/api/auth/login", json={"password": PASSWORD})
        assert accepted.status_code == 200
        assert accepted.json()["user"]["display_name"] == "Admin"
        assert accepted.headers["Cache-Control"] == "no-store"
        assert client.cookies.get(settings.session_cookie_name)
        assert client.cookies.get(settings.csrf_cookie_name)
        assert client.get("/api/consultants").status_code == 200

        missing_csrf = client.post("/api/consultants", json={"name": "Dr Test", "post_title": None})
        assert missing_csrf.status_code == 403
        assert missing_csrf.json()["error"]["code"] == "csrf_failed"

        created = client.post(
            "/api/consultants",
            json={"name": "Dr Test", "post_title": None},
            headers=csrf_headers(client),
        )
        assert created.status_code == 201

        cross_origin = client.post(
            "/api/auth/logout",
            headers=csrf_headers(client, origin="https://attacker.example"),
        )
        assert cross_origin.status_code == 403

        logged_out = client.post("/api/auth/logout", headers=csrf_headers(client))
        assert logged_out.status_code == 200
        assert logged_out.json() == {"authenticated": False, "user": None}
        assert client.get("/api/consultants").status_code == 401

    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            events = tuple(session.scalars(select(SecurityEvent).order_by(SecurityEvent.id)))
            assert [event.event_type for event in events] == [
                "account_created",
                "login_failed",
                "login_succeeded",
                "logout",
            ]
            stored_sessions = tuple(session.scalars(select(UserSession)))
            assert len(stored_sessions) == 1
            assert stored_sessions[0].revoked_at is not None
    finally:
        engine.dispose()


def test_password_reset_and_disable_invalidate_every_session(tmp_path: Path) -> None:
    app, settings = configured_app(tmp_path)
    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"password": PASSWORD}).status_code == 200

        engine = create_database_engine(settings.resolved_database_url)
        try:
            with session_scope(create_session_factory(engine)) as session:
                reset_admin_password(session, NEW_PASSWORD)
        finally:
            engine.dispose()

        assert client.get("/api/consultants").status_code == 401
        assert client.post("/api/auth/login", json={"password": PASSWORD}).status_code == 401
        assert client.post("/api/auth/login", json={"password": NEW_PASSWORD}).status_code == 200

        engine = create_database_engine(settings.resolved_database_url)
        try:
            with session_scope(create_session_factory(engine)) as session:
                set_admin_enabled(session, enabled=False)
        finally:
            engine.dispose()

        assert client.get("/api/consultants").status_code == 401
        assert client.post("/api/auth/login", json={"password": NEW_PASSWORD}).status_code == 401


def test_session_tokens_are_hashed_and_expire_server_side(tmp_path: Path) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        factory = create_session_factory(engine)
        moment = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        with session_scope(factory) as session:
            user = create_admin(session, PASSWORD)
            tokens = create_session(session, user, lifetime=timedelta(hours=12), now=moment)

        with session_scope(factory) as session:
            stored = session.scalar(select(UserSession))
            assert stored is not None
            assert stored.token_hash != tokens.session_token
            assert stored.csrf_token_hash != tokens.csrf_token
            assert len(stored.token_hash) == 64
            assert (
                authenticated_user(session, tokens.session_token, now=moment + timedelta(hours=12))
                is None
            )
    finally:
        engine.dispose()


def test_shared_admin_can_hold_multiple_active_sessions(tmp_path: Path) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        factory = create_session_factory(engine)
        with session_scope(factory) as session:
            user = create_admin(session, PASSWORD)
            first = create_session(session, user, lifetime=timedelta(hours=12))
            second = create_session(session, user, lifetime=timedelta(hours=12))

        with session_scope(factory) as session:
            assert authenticated_user(session, first.session_token) is not None
            assert authenticated_user(session, second.session_token) is not None
            assert len(tuple(session.scalars(select(UserSession)))) == 2
    finally:
        engine.dispose()


def test_admin_password_policy(tmp_path: Path) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            try:
                create_admin(session, "x" * (MINIMUM_PASSWORD_LENGTH - 1))
            except ValueError as error:
                assert "at least 10 characters" in str(error)
            else:
                raise AssertionError("Short Admin password was accepted")
    finally:
        engine.dispose()


def test_five_consecutive_failures_lock_admin_for_fifteen_minutes(tmp_path: Path) -> None:
    app, settings = configured_app(tmp_path)
    with TestClient(app) as client:
        for _attempt in range(4):
            response = client.post("/api/auth/login", json={"password": "wrong-password"})
            assert response.status_code == 401

        locked = client.post("/api/auth/login", json={"password": "wrong-password"})
        assert locked.status_code == 429
        assert locked.json()["error"]["details"] == {"retry_after_seconds": 900}

        still_locked = client.post("/api/auth/login", json={"password": PASSWORD})
        assert still_locked.status_code == 429

        engine = create_database_engine(settings.resolved_database_url)
        try:
            with session_scope(create_session_factory(engine)) as session:
                user = admin_user(session)
                assert user is not None
                user.locked_until = datetime.now(UTC) - timedelta(seconds=1)
        finally:
            engine.dispose()

        accepted = client.post("/api/auth/login", json={"password": PASSWORD})
        assert accepted.status_code == 200


def test_lockout_counter_uses_consecutive_failures(tmp_path: Path) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            user = create_admin(session, PASSWORD)
            moment = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
            locked_for = 0
            for attempt in range(1, 6):
                locked_for = record_failed_login(user, now=moment)
                assert user.failed_login_count == attempt
            assert locked_for == 900
            assert lockout_remaining_seconds(user, now=moment + timedelta(minutes=14)) == 60
            assert lockout_remaining_seconds(user, now=moment + timedelta(minutes=15)) == 0
            assert user.failed_login_count == 0
            assert user.locked_until is None
            membership = session.scalar(
                select(WorkspaceMembership).where(WorkspaceMembership.user_id == user.id)
            )
            assert membership is not None
            assert membership.role == "admin"
    finally:
        engine.dispose()


def test_server_admin_command_creates_resets_disables_and_enables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)
    passwords = iter((PASSWORD, NEW_PASSWORD))
    monkeypatch.setattr(admin_command, "confirmed_password", lambda: next(passwords))

    admin_command.run("create", settings)
    admin_command.run("reset-password", settings)
    admin_command.run("disable", settings)
    admin_command.run("enable", settings)

    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            user = admin_user(session)
            assert user is not None
            assert user.display_name == "Admin"
            assert user.enabled
            assert user.password_version == 2
            assert user.failed_login_count == 0
            assert user.locked_until is None
            events = tuple(session.scalars(select(SecurityEvent).order_by(SecurityEvent.id)))
            assert [event.event_type for event in events] == [
                "account_created",
                "password_reset",
                "account_disabled",
                "account_enabled",
            ]
    finally:
        engine.dispose()


def test_production_authentication_and_secure_cookie_contract() -> None:
    database = SecretStr("postgresql+psycopg://leave_planner:secret@database/leave_planner")
    with pytest.raises(ValidationError, match="Production requires authentication"):
        Settings(environment="production", database_url=database, authentication_required=False)

    settings = Settings(environment="production", database_url=database)
    response = Response()
    set_authentication_cookies(response, settings, "session-token", "csrf-token")
    cookie_headers = response.headers.getlist("set-cookie")
    assert any(
        "__Host-id=session-token" in header
        and "HttpOnly" in header
        and "SameSite=strict" in header
        and "Secure" in header
        for header in cookie_headers
    )
    assert any(
        "__Host-csrf=csrf-token" in header
        and "HttpOnly" not in header
        and "SameSite=strict" in header
        and "Secure" in header
        for header in cookie_headers
    )
