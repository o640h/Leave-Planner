"""Opt-in integration checks against a real PostgreSQL database."""

import os

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import inspect

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
