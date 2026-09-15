"""First Owner workspace setup and session-lifecycle acceptance tests."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine

from authentication import account_admin
from authentication.models import ACTIVE, User, UserSession
from authentication.service import (
    account_for_email,
    create_account,
    create_session,
    reset_account_password,
)
from consultants.models import Consultant
from database import create_database_engine, create_session_factory, session_scope
from main import create_app
from migrations import upgrade_database
from settings import Settings
from workspaces.models import OWNER_ROLE, Workspace, WorkspaceMembership
from workspaces.service import create_initial_owner_workspace

EMAIL = "owner@example.org"
PASSWORD = "owner-password"
NEW_PASSWORD = "replacement-password"


def configured_database(tmp_path: Path) -> tuple[Settings, Engine]:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    return settings, engine


def test_existing_account_receives_one_new_empty_owner_workspace_and_is_idempotent(
    tmp_path: Path,
) -> None:
    _settings, engine = configured_database(tmp_path)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            account = create_account(
                session,
                display_name="Primary Owner",
                email=EMAIL,
                password=PASSWORD,
                verified_at=datetime.now(UTC),
            )
            create_session(session, account, lifetime=timedelta(hours=12))
            create_session(session, account, lifetime=timedelta(hours=12))

        with session_scope(factory) as session:
            result = create_initial_owner_workspace(
                session,
                email=EMAIL,
                password=PASSWORD,
                workspace_name="Clinical Leave Team",
            )
            assert result.created is True
            assert result.workspace.name == "Clinical Leave Team"

        with session_scope(factory) as session:
            loaded_account = account_for_email(session, EMAIL)
            membership = session.scalar(select(WorkspaceMembership))
            assert loaded_account is not None
            assert membership is not None
            assert membership.user_id == loaded_account.id
            assert membership.role == OWNER_ROLE
            assert loaded_account.last_workspace_id == membership.workspace_id
            assert session.scalar(select(func.count()).select_from(Workspace)) == 1
            assert session.scalar(select(func.count()).select_from(WorkspaceMembership)) == 1
            assert all(
                stored.revoked_at is not None for stored in session.scalars(select(UserSession))
            )
            for table in ("consultants", "holiday_corrections", "audit_events"):
                assert session.scalar(text(f"SELECT COUNT(*) FROM {table}")) == 0

            repeated = create_initial_owner_workspace(
                session,
                email=EMAIL,
                password=PASSWORD,
                workspace_name="Clinical Leave Team",
            )
            assert repeated.created is False
            assert repeated.workspace.id == membership.workspace_id
    finally:
        engine.dispose()


def test_owner_can_use_independent_sessions_and_password_recovery_revokes_both(
    tmp_path: Path,
) -> None:
    settings, engine = configured_database(tmp_path)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            create_initial_owner_workspace(
                session,
                display_name="Primary Owner",
                email=EMAIL,
                password=PASSWORD,
                workspace_name="Clinical Leave Team",
            )

        app = create_app(settings=settings, frontend_dist=tmp_path / "missing-frontend")
        with TestClient(app) as first, TestClient(app) as second:
            for client in (first, second):
                response = client.post(
                    "/api/auth/login",
                    json={"email": EMAIL, "password": PASSWORD},
                )
                assert response.status_code == 200
                assert response.json()["workspace"]["state"] == "active"
                assert response.json()["workspace"]["memberships"][0]["role"] == OWNER_ROLE

            first_csrf = first.cookies.get("leave_planner_csrf")
            assert first_csrf
            assert (
                first.post(
                    "/api/auth/logout",
                    headers={"Origin": "http://testserver", "X-CSRF-Token": first_csrf},
                ).status_code
                == 200
            )
            assert second.get("/api/auth/session").json()["authenticated"] is True

            with session_scope(factory) as session:
                account = account_for_email(session, EMAIL)
                assert account is not None
                reset_account_password(session, account, NEW_PASSWORD)

            assert second.get("/api/auth/session").json()["authenticated"] is False
            recovered = second.post(
                "/api/auth/login",
                json={"email": EMAIL, "password": NEW_PASSWORD},
            )
            assert recovered.status_code == 200
            assert recovered.json()["workspace"]["state"] == "active"
    finally:
        engine.dispose()


def test_wrong_password_or_legacy_data_leaves_the_clean_start_unchanged(tmp_path: Path) -> None:
    _settings, engine = configured_database(tmp_path)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            create_account(
                session,
                display_name="Primary Owner",
                email=EMAIL,
                password=PASSWORD,
                verified_at=datetime.now(UTC),
            )

        with (
            pytest.raises(ValueError, match="password could not be verified"),
            session_scope(factory) as session,
        ):
            create_initial_owner_workspace(
                session,
                email=EMAIL,
                password="wrong-password",
                workspace_name="Clinical Leave Team",
            )

        with session_scope(factory) as session:
            placeholder = session.scalar(select(Workspace))
            assert placeholder is not None
            session.add(Consultant(workspace_id=placeholder.id, name="Must Not Be Inherited"))

        with (
            pytest.raises(ValueError, match="legacy business data remains"),
            session_scope(factory) as session,
        ):
            create_initial_owner_workspace(
                session,
                email=EMAIL,
                password=PASSWORD,
                workspace_name="Clinical Leave Team",
            )

        with session_scope(factory) as session:
            assert session.scalar(select(func.count()).select_from(User)) == 1
            assert session.scalar(select(func.count()).select_from(Workspace)) == 1
            assert session.scalar(select(func.count()).select_from(WorkspaceMembership)) == 0
            assert session.scalar(select(func.count()).select_from(Consultant)) == 1
    finally:
        engine.dispose()


def test_operator_command_creates_the_first_owner_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)
    entries = iter((EMAIL, "Primary Owner", "Clinical Leave Team"))
    passwords = iter((PASSWORD, PASSWORD))
    monkeypatch.setattr("builtins.input", lambda _prompt: next(entries))
    monkeypatch.setattr(account_admin, "getpass", lambda _prompt: next(passwords))

    account_admin.run("create-owner", settings)

    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            account = account_for_email(session, EMAIL)
            membership = session.scalar(select(WorkspaceMembership))
            assert account is not None
            assert account.security_state == ACTIVE
            assert account.email_verified_at is not None
            assert membership is not None
            assert membership.user_id == account.id
            assert membership.role == OWNER_ROLE
    finally:
        engine.dispose()
