"""Adversarial proofs for the private workspace authorization boundary."""

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

from alembic import command
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import delete, select

from audit import AuditEvent
from authentication.service import admin_user, create_admin, set_admin_enabled
from consultants.models import Consultant
from database import create_database_engine, create_session_factory, session_scope
from leave_years.models import LeaveYear
from main import create_app
from migrations import alembic_config, upgrade_database
from public_holidays.persistence import HolidayCorrectionRecord
from settings import Settings
from workspaces.models import Workspace, WorkspaceMembership

PASSWORD = "shared-admin-password"


def configured_app(tmp_path: Path) -> tuple[FastAPI, Settings]:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            create_admin(session, PASSWORD)
    finally:
        engine.dispose()
    return create_app(settings=settings, frontend_dist=tmp_path / "missing-frontend"), settings


def sign_in(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"password": PASSWORD})
    assert response.status_code == 200
    csrf = client.cookies.get("leave_planner_csrf")
    assert csrf
    return {"X-CSRF-Token": csrf, "Origin": "http://testserver"}


def protected_surface_attempts(
    client: TestClient, headers: dict[str, str] | None = None
) -> tuple[Response, ...]:
    request_headers = headers or {}
    return (
        client.get("/api/consultants"),
        client.post(
            "/api/consultants",
            json={"name": "Denied", "post_title": None},
            headers=request_headers,
        ),
        client.get("/api/consultants/1/leave-years/1/summary"),
        client.get("/api/consultants/1/leave-years/1/leave-log.pdf"),
        client.delete(
            "/api/consultants/1/leave-years/1/bookings/1",
            headers=request_headers,
        ),
        client.get("/api/settings/public-holidays"),
    )


def test_unauthenticated_session_cannot_use_any_data_surface(tmp_path: Path) -> None:
    app, _settings = configured_app(tmp_path)
    with TestClient(app) as client:
        for response in protected_surface_attempts(client):
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "authentication_required"


def test_disabled_admin_cannot_use_any_data_surface(tmp_path: Path) -> None:
    app, settings = configured_app(tmp_path)
    with TestClient(app) as client:
        headers = sign_in(client)
        engine = create_database_engine(settings.resolved_database_url)
        try:
            with session_scope(create_session_factory(engine)) as session:
                set_admin_enabled(session, enabled=False)
        finally:
            engine.dispose()

        for response in protected_surface_attempts(client, headers):
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "authentication_required"


def test_authenticated_user_without_membership_cannot_use_any_data_surface(
    tmp_path: Path,
) -> None:
    app, settings = configured_app(tmp_path)
    with TestClient(app) as client:
        headers = sign_in(client)

        engine = create_database_engine(settings.resolved_database_url)
        try:
            with session_scope(create_session_factory(engine)) as session:
                user = admin_user(session)
                assert user is not None
                session.execute(
                    delete(WorkspaceMembership).where(WorkspaceMembership.user_id == user.id)
                )
        finally:
            engine.dispose()

        for response in protected_surface_attempts(client, headers):
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "workspace_access_denied"
        recovery = client.post("/api/settings/recovery/backups", headers=headers)
        assert recovery.status_code == (403 if settings.uses_sqlite else 404)


def test_foreign_workspace_records_are_not_visible_or_mutable(tmp_path: Path) -> None:
    app, settings = configured_app(tmp_path)
    with TestClient(app) as client:
        headers = sign_in(client)
        owned = client.post(
            "/api/consultants",
            json={"name": "Owned Consultant", "post_title": None},
            headers=headers,
        )
        assert owned.status_code == 201
        owned_id = int(owned.json()["id"])
        owned_year = client.post(
            f"/api/consultants/{owned_id}/leave-years",
            json={"start_date": "2025-08-29", "end_date": "2026-08-28"},
            headers=headers,
        )
        assert owned_year.status_code == 201

        engine = create_database_engine(settings.resolved_database_url)
        try:
            with session_scope(create_session_factory(engine)) as session:
                owned_event = session.scalar(
                    select(AuditEvent).where(AuditEvent.consultant_id == owned_id)
                )
                user = admin_user(session)
                membership = session.scalar(select(WorkspaceMembership))
                assert owned_event is not None
                assert user is not None
                assert membership is not None
                assert owned_event.workspace_id == membership.workspace_id
                assert owned_event.actor_user_id == user.id
                assert owned_event.actor_label == "Admin"

                foreign_workspace = Workspace(name="Foreign Workspace")
                session.add(foreign_workspace)
                session.flush()
                foreign_consultant = Consultant(
                    workspace_id=foreign_workspace.id,
                    name="Foreign Consultant",
                )
                session.add(foreign_consultant)
                session.flush()
                foreign_year = LeaveYear(
                    consultant_id=foreign_consultant.id,
                    start_date=date(2025, 8, 29),
                    end_date=date(2026, 8, 28),
                )
                foreign_correction = HolidayCorrectionRecord(
                    workspace_id=foreign_workspace.id,
                    holiday_date=date(2026, 1, 2),
                    action="add",
                    replacement_name="Foreign Holiday",
                    reason="Foreign correction",
                )
                session.add_all((foreign_year, foreign_correction))
                session.flush()
                session.add(
                    AuditEvent(
                        workspace_id=foreign_workspace.id,
                        actor_user_id=None,
                        actor_label="Foreign Admin",
                        consultant_id=foreign_consultant.id,
                        entity_type="consultant",
                        entity_id=foreign_consultant.id,
                        action="updated",
                        details="{}",
                    )
                )
                foreign_consultant_id = foreign_consultant.id
                foreign_year_id = foreign_year.id
                foreign_correction_id = foreign_correction.id
        finally:
            engine.dispose()

        directory = client.get("/api/consultants")
        assert directory.status_code == 200
        assert [item["name"] for item in directory.json()] == ["Owned Consultant"]

        foreign_root = f"/api/consultants/{foreign_consultant_id}"
        foreign_year_root = f"{foreign_root}/leave-years/{foreign_year_id}"
        attempts = (
            client.get(foreign_root),
            client.put(
                foreign_root,
                json={"name": "Stolen", "post_title": None},
                headers=headers,
            ),
            client.get(f"{foreign_root}/archive-impact"),
            client.post(
                f"{foreign_root}/archive",
                json={"confirmation": "Foreign Consultant"},
                headers=headers,
            ),
            client.get(f"{foreign_root}/leave-years"),
            client.get(f"{foreign_year_root}/summary"),
            client.get(f"{foreign_year_root}/leave-log.pdf"),
            client.get(f"{foreign_year_root}/job-plans"),
            client.get(f"{foreign_year_root}/planning"),
            client.delete(f"{foreign_year_root}/bookings/1", headers=headers),
            client.get(f"{foreign_year_root}/public-holidays"),
        )
        for response in attempts:
            assert response.status_code == 404

        holiday_settings = client.get("/api/settings/public-holidays")
        assert holiday_settings.status_code == 200
        assert holiday_settings.json()["corrections"] == []
        denied_correction = client.delete(
            f"/api/settings/public-holidays/corrections/{foreign_correction_id}",
            headers=headers,
        )
        assert denied_correction.status_code == 404


def test_workspace_migration_backfills_existing_roots_and_admin_membership(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "pre-workspace.sqlite3"
    config = alembic_config(database_path)
    command.upgrade(config, "0013")

    with closing(sqlite3.connect(database_path)) as connection, connection:
        connection.execute(
            "INSERT INTO users (id, display_name, password_hash) VALUES (1, 'Admin', 'hash')"
        )
        connection.execute("INSERT INTO consultants (id, name) VALUES (1, 'Existing')")
        connection.execute(
            """
            INSERT INTO audit_events (
                consultant_id, entity_type, entity_id, action, details
            ) VALUES (1, 'consultant', 1, 'updated', '{}')
            """
        )
        connection.execute(
            """
            INSERT INTO holiday_corrections (
                holiday_date, action, replacement_name, reason
            ) VALUES ('2026-01-02', 'add', 'Existing Holiday', 'Existing correction')
            """
        )

    command.upgrade(config, "head")

    with closing(sqlite3.connect(database_path)) as connection, connection:
        workspace_id = connection.execute("SELECT id FROM workspaces").fetchone()[0]
        assert connection.execute(
            "SELECT workspace_id, user_id, role FROM workspace_memberships"
        ).fetchone() == (workspace_id, 1, "admin")
        assert connection.execute(
            "SELECT workspace_id FROM consultants WHERE id = 1"
        ).fetchone() == (workspace_id,)
        assert connection.execute("SELECT workspace_id FROM holiday_corrections").fetchone() == (
            workspace_id,
        )
        assert connection.execute(
            "SELECT workspace_id, actor_user_id, actor_label FROM audit_events"
        ).fetchone() == (workspace_id, None, "System Import")
