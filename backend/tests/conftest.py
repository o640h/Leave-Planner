"""Shared test configuration, including opt-in PostgreSQL suite execution."""

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import text

from database import create_database_engine, database_url

POSTGRES_TEST_URL = os.environ.get("LEAVE_PLANNER_TEST_POSTGRES_URL")

if POSTGRES_TEST_URL:
    os.environ["LEAVE_PLANNER_DATABASE_URL"] = POSTGRES_TEST_URL


@pytest.fixture(autouse=True)
def isolated_postgresql_database(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Reset the opt-in PostgreSQL schema once per test or retain SQLite-only behavior."""

    if request.node.get_closest_marker("sqlite_only") is not None:
        monkeypatch.delenv("LEAVE_PLANNER_DATABASE_URL", raising=False)
        yield
        return

    if not POSTGRES_TEST_URL:
        yield
        return

    engine = create_database_engine(database_url(POSTGRES_TEST_URL))
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        yield
    finally:
        engine.dispose()
