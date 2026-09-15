"""Email identity, session, CSRF, and clean-start migration tests."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from authentication import account_admin
from authentication.models import ACTIVE, DISABLED, SecurityEvent, UserSession
from authentication.passwords import MINIMUM_PASSWORD_LENGTH
from authentication.router import set_authentication_cookies
from authentication.service import (
    account_for_email,
    authenticated_user,
    create_account,
    create_session,
    lockout_remaining_seconds,
    normalise_email,
    reset_account_password,
    set_account_state,
)
from database import create_database_engine, create_session_factory, session_scope
from main import create_app
from migrations import alembic_config, upgrade_database
from settings import Settings
from workspaces.models import ADMIN_ROLE, Workspace, WorkspaceMembership

EMAIL = "Operator@Example.org"
PASSWORD = "individual-account-password"
NEW_PASSWORD = "replacement-password"


def configured_app(data_dir: Path) -> tuple[FastAPI, Settings]:
    settings = Settings(environment="test", data_dir=data_dir)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            account = create_account(
                session,
                display_name="Primary Operator",
                email=EMAIL,
                password=PASSWORD,
                verified_at=datetime.now(UTC),
            )
            workspace = session.scalar(select(Workspace))
            assert workspace is not None
            session.add(
                WorkspaceMembership(
                    workspace_id=workspace.id,
                    user_id=account.id,
                    role=ADMIN_ROLE,
                )
            )
            account.last_workspace_id = workspace.id
    finally:
        engine.dispose()
    return create_app(settings=settings, frontend_dist=data_dir / "missing-frontend"), settings


def csrf_headers(client: TestClient, *, origin: str = "http://testserver") -> dict[str, str]:
    token = client.cookies.get("leave_planner_csrf")
    assert token
    return {"X-CSRF-Token": token, "Origin": origin}


def credentials(email: str = EMAIL, password: str = PASSWORD) -> dict[str, str]:
    return {"email": email, "password": password}


def test_email_login_protects_application_and_logout_revokes_session(tmp_path: Path) -> None:
    app, settings = configured_app(tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/consultants").status_code == 401
        assert client.get("/api/auth/session").json() == {
            "authenticated": False,
            "user": None,
            "workspace": None,
        }

        rejected = client.post("/api/auth/login", json=credentials(password="incorrect-password"))
        assert rejected.status_code == 401
        assert rejected.json()["error"]["message"] == "The email or password is incorrect."
        assert rejected.headers["Cache-Control"] == "no-store"

        cross_origin = client.post(
            "/api/auth/login",
            json=credentials(),
            headers={"Origin": "https://attacker.example"},
        )
        assert cross_origin.status_code == 403

        accepted = client.post("/api/auth/login", json=credentials(email="operator@example.ORG"))
        assert accepted.status_code == 200
        assert accepted.json()["user"] == {
            "public_id": accepted.json()["user"]["public_id"],
            "display_name": "Primary Operator",
            "display_email": EMAIL,
        }
        assert len(accepted.json()["user"]["public_id"]) == 32
        assert client.cookies.get(settings.session_cookie_name)
        assert client.cookies.get(settings.csrf_cookie_name)
        assert client.get("/api/consultants").status_code == 200

        missing_csrf = client.post("/api/consultants", json={"name": "Dr Test"})
        assert missing_csrf.status_code == 403

        created = client.post(
            "/api/consultants",
            json={"name": "Dr Test", "post_title": None},
            headers=csrf_headers(client),
        )
        assert created.status_code == 201

        logged_out = client.post("/api/auth/logout", headers=csrf_headers(client))
        assert logged_out.status_code == 200
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
            assert all(EMAIL not in event.details for event in events)
            stored = session.scalar(select(UserSession))
            assert stored is not None and stored.revoked_at is not None
    finally:
        engine.dispose()


def test_canonical_email_is_unique_while_display_names_are_not(tmp_path: Path) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            first = create_account(
                session,
                display_name="Same Name",
                email="First.Person@Example.org",
                password=PASSWORD,
            )
            second = create_account(
                session,
                display_name="Same Name",
                email="other@example.org",
                password=PASSWORD,
            )
            assert first.public_id != second.public_id
            assert first.canonical_email == "first.person@example.org"
            assert first.display_email == "First.Person@Example.org"

        with (
            pytest.raises((ValueError, IntegrityError)),
            session_scope(create_session_factory(engine)) as session,
        ):
            create_account(
                session,
                display_name="Different Name",
                email="FIRST.PERSON@example.ORG",
                password=PASSWORD,
            )
    finally:
        engine.dispose()


def test_email_validation_does_not_apply_provider_specific_rewriting() -> None:
    assert normalise_email(" First.Last+Leave@gmail.com ").canonical == (
        "first.last+leave@gmail.com"
    )
    with pytest.raises(ValueError, match="valid email"):
        normalise_email("not-an-email")


def test_unknown_unverified_disabled_locked_and_wrong_password_are_indistinguishable(
    tmp_path: Path,
) -> None:
    app, settings = configured_app(tmp_path)
    payloads = (
        credentials(email="unknown@example.org"),
        credentials(password="wrong-password"),
    )
    with TestClient(app) as client:
        responses = [client.post("/api/auth/login", json=payload) for payload in payloads]

        engine = create_database_engine(settings.resolved_database_url)
        try:
            with session_scope(create_session_factory(engine)) as session:
                account = account_for_email(session, EMAIL)
                assert account is not None
                set_account_state(session, account, DISABLED)
        finally:
            engine.dispose()
        responses.append(client.post("/api/auth/login", json=credentials()))

    pending_settings = Settings(environment="test", data_dir=tmp_path / "pending")
    upgrade_database(pending_settings.resolved_database_url)
    pending_engine = create_database_engine(pending_settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(pending_engine)) as session:
            create_account(
                session,
                display_name="Pending",
                email="pending@example.org",
                password=PASSWORD,
            )
    finally:
        pending_engine.dispose()
    with TestClient(
        create_app(settings=pending_settings, frontend_dist=tmp_path / "missing")
    ) as client:
        responses.append(
            client.post(
                "/api/auth/login",
                json=credentials(email="pending@example.org"),
            )
        )

    assert {(response.status_code, response.json()["error"]["code"]) for response in responses} == {
        (401, "invalid_credentials")
    }
    assert {response.json()["error"]["message"] for response in responses} == {
        "The email or password is incorrect."
    }


def test_five_failures_lock_one_account_without_disclosing_lockout(tmp_path: Path) -> None:
    app, settings = configured_app(tmp_path)
    with TestClient(app) as client:
        for _attempt in range(5):
            response = client.post("/api/auth/login", json=credentials(password="wrong-password"))
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "invalid_credentials"

        assert client.post("/api/auth/login", json=credentials()).status_code == 401

        engine = create_database_engine(settings.resolved_database_url)
        try:
            with session_scope(create_session_factory(engine)) as session:
                account = account_for_email(session, EMAIL)
                assert account is not None
                assert account.failed_login_count == 5
                assert lockout_remaining_seconds(account) > 0
                account.locked_until = datetime.now(UTC) - timedelta(seconds=1)
        finally:
            engine.dispose()

        assert client.post("/api/auth/login", json=credentials()).status_code == 200


def test_password_reset_and_state_change_revoke_every_session(tmp_path: Path) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        factory = create_session_factory(engine)
        with session_scope(factory) as session:
            account = create_account(
                session,
                display_name="Operator",
                email=EMAIL,
                password=PASSWORD,
                verified_at=datetime.now(UTC),
            )
            first = create_session(session, account, lifetime=timedelta(hours=12))
            second = create_session(session, account, lifetime=timedelta(hours=12))

        with session_scope(factory) as session:
            stored_account = account_for_email(session, EMAIL)
            assert stored_account is not None
            reset_account_password(session, stored_account, NEW_PASSWORD)

        with session_scope(factory) as session:
            assert authenticated_user(session, first.session_token) is None
            assert authenticated_user(session, second.session_token) is None
            stored_account = account_for_email(session, EMAIL)
            assert stored_account is not None
            replacement = create_session(session, stored_account, lifetime=timedelta(hours=12))
            set_account_state(session, stored_account, DISABLED)

        with session_scope(factory) as session:
            assert authenticated_user(session, replacement.session_token) is None
    finally:
        engine.dispose()


def test_session_tokens_are_hashed_and_expire_server_side(tmp_path: Path) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        factory = create_session_factory(engine)
        moment = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
        with session_scope(factory) as session:
            account = create_account(
                session,
                display_name="Operator",
                email=EMAIL,
                password=PASSWORD,
                verified_at=moment,
            )
            tokens = create_session(session, account, lifetime=timedelta(hours=12), now=moment)

        with session_scope(factory) as session:
            stored = session.scalar(select(UserSession))
            assert stored is not None
            assert stored.token_hash != tokens.session_token
            assert stored.csrf_token_hash != tokens.csrf_token
            assert (
                authenticated_user(session, tokens.session_token, now=moment + timedelta(hours=12))
                is None
            )
    finally:
        engine.dispose()


def test_unverified_account_cannot_be_enabled(tmp_path: Path) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            account = create_account(
                session,
                display_name="Pending Operator",
                email="pending@example.org",
                password=PASSWORD,
            )
            with pytest.raises(ValueError, match="verified email"):
                set_account_state(session, account, ACTIVE)
    finally:
        engine.dispose()


def test_password_policy_uses_account_language(tmp_path: Path) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with (
            pytest.raises(ValueError, match="password must contain at least 8"),
            session_scope(create_session_factory(engine)) as session,
        ):
            create_account(
                session,
                display_name="Operator",
                email=EMAIL,
                password="x" * (MINIMUM_PASSWORD_LENGTH - 1),
            )
    finally:
        engine.dispose()


@pytest.mark.sqlite_only
def test_clean_start_migration_discards_empty_shared_account_boundary(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    config = alembic_config(path)
    command.upgrade(config, "0014")
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "INSERT INTO users (id, display_name, password_hash) VALUES (1, 'Admin', 'hash')"
        )
        workspace_id = connection.execute("SELECT id FROM workspaces").fetchone()[0]
        connection.execute(
            "INSERT INTO workspace_memberships (workspace_id, user_id, role) "
            "VALUES (?, 1, 'admin')",
            (workspace_id,),
        )

    command.upgrade(config, "head")

    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone() == (0,)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        assert {"public_id", "canonical_email", "display_email", "security_state"} <= columns
        assert "enabled" not in columns


@pytest.mark.sqlite_only
def test_clean_start_migration_refuses_legacy_business_data(tmp_path: Path) -> None:
    path = tmp_path / "occupied.sqlite3"
    config = alembic_config(path)
    command.upgrade(config, "0014")
    with closing(sqlite3.connect(path)) as connection, connection:
        workspace_id = connection.execute("SELECT id FROM workspaces").fetchone()[0]
        connection.execute(
            "INSERT INTO consultants (id, workspace_id, name) VALUES (1, ?, 'Retained')",
            (workspace_id,),
        )

    with pytest.raises(RuntimeError, match="legacy business data remains"):
        command.upgrade(config, "head")


def test_server_account_command_creates_resets_disables_and_enables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)
    entries = iter(("Primary Operator", EMAIL, EMAIL, EMAIL, EMAIL))
    passwords = iter((PASSWORD, PASSWORD, NEW_PASSWORD, NEW_PASSWORD))
    monkeypatch.setattr("builtins.input", lambda _prompt: next(entries))
    monkeypatch.setattr(account_admin, "getpass", lambda _prompt: next(passwords))

    account_admin.run("create", settings)
    account_admin.run("reset-password", settings)
    account_admin.run("disable", settings)
    account_admin.run("enable", settings)

    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            account = account_for_email(session, EMAIL)
            assert account is not None
            assert account.display_name == "Primary Operator"
            assert account.security_state == ACTIVE
            assert account.email_verified_at is not None
            assert account.password_version == 2
            assert session.scalar(select(UserSession)) is None
    finally:
        engine.dispose()


def test_production_authentication_and_secure_cookie_contract() -> None:
    database = SecretStr("postgresql+psycopg://leave_planner:secret@database/leave_planner")
    with pytest.raises(ValidationError, match="Production requires authentication"):
        Settings(environment="production", database_url=database, authentication_required=False)

    settings = Settings(
        environment="production",
        database_url=database,
        email_provider="resend",
        resend_api_key_file=Path(__file__),
    )
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
