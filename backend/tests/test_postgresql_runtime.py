"""Opt-in integration checks against a real PostgreSQL database."""

import os

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from database import create_database_engine, database_url
from main import create_app
from migrations import upgrade_database
from settings import Settings

POSTGRES_TEST_URL = os.environ.get("LEAVE_PLANNER_TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="Set LEAVE_PLANNER_TEST_POSTGRES_URL to run PostgreSQL integration checks",
)


def test_postgresql_migrations_and_api_round_trip() -> None:
    assert POSTGRES_TEST_URL is not None
    url = database_url(POSTGRES_TEST_URL)
    upgrade_database(url)
    engine = create_database_engine(url)
    try:
        assert {"alembic_version", "consultants", "leave_bookings"} <= set(
            inspect(engine).get_table_names()
        )
    finally:
        engine.dispose()

    app = create_app(
        settings=Settings(
            environment="test",
            database_url=SecretStr(POSTGRES_TEST_URL),
            authentication_required=False,
        ),
        frontend_dist=Settings(environment="test").resolved_data_dir / "missing-frontend",
    )
    with TestClient(app) as client:
        created = client.post(
            "/api/consultants",
            json={"name": "PostgreSQL Example", "post_title": "Consultant"},
        )
        assert created.status_code == 201
        assert client.get("/api/consultants").json() == [created.json()]
        assert client.get("/api/settings/recovery").status_code == 404


def test_postgresql_application_role_rls_requires_workspace_context() -> None:
    assert POSTGRES_TEST_URL is not None
    url = database_url(POSTGRES_TEST_URL)
    upgrade_database(url)
    engine = create_database_engine(url)
    try:
        with engine.begin() as connection:
            protected_rows = connection.execute(
                text(
                    "SELECT relname, relrowsecurity FROM pg_class "
                    "WHERE relname IN ('workspaces', 'workspace_memberships', "
                    "'consultants', 'holiday_corrections', 'audit_events')"
                )
            )
            protected: dict[str, bool] = {
                str(name): bool(enabled) for name, enabled in protected_rows.tuples()
            }
            assert protected == {
                "audit_events": True,
                "consultants": True,
                "holiday_corrections": True,
                "workspace_memberships": True,
                "workspaces": True,
            }
            role_exists = connection.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_roles "
                    "WHERE rolname = 'leave_planner_application')"
                )
            )
            if not role_exists:
                pytest.skip("The disposable PostgreSQL cluster has no application role")
            can_set_role = connection.scalar(
                text(
                    "SELECT pg_has_role(current_user, 'leave_planner_application', 'USAGE') "
                    "OR (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)"
                )
            )
            if not can_set_role:
                pytest.skip("The PostgreSQL test role cannot assume the application role")
            connection.execute(
                text(
                    "INSERT INTO consultants (workspace_id, name) "
                    "VALUES (1, 'RLS Proof')"
                )
            )

        with engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text("SET LOCAL ROLE leave_planner_application"))
            assert connection.scalar(text("SELECT count(*) FROM consultants")) == 0
            connection.execute(
                text("SELECT set_config('leave_planner.workspace_id', '1', true)")
            )
            assert connection.scalar(text("SELECT count(*) FROM consultants")) == 1
            transaction.rollback()

        with engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text("SET LOCAL ROLE leave_planner_application"))
            with pytest.raises(DBAPIError):
                connection.execute(
                    text(
                        "INSERT INTO consultants (workspace_id, name) "
                        "VALUES (1, 'Denied Without Context')"
                    )
                )
            transaction.rollback()
    finally:
        engine.dispose()
