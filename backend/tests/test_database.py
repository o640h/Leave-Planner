"""Database migration and online backup smoke tests."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from backup import create_online_backup
from database import create_database_engine, create_session_factory, session_scope
from migrations import upgrade_database


def test_alembic_upgrade_creates_foundation_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "migrated.sqlite3"

    upgrade_database(database_path)

    engine = create_database_engine(database_path)
    assert {
        "alembic_version",
        "system_metadata",
        "consultants",
        "leave_years",
        "audit_events",
        "job_plan_versions",
        "job_plan_days",
    } <= set(inspect(engine).get_table_names())
    job_plan_columns = {
        column["name"] for column in inspect(engine).get_columns("job_plan_versions")
    }
    assert "additional_dcc_hours" not in job_plan_columns
    assert "additional_spa_hours" not in job_plan_columns
    engine.dispose()


def test_sqlite_engine_enables_integrity_pragmas(tmp_path: Path) -> None:
    engine = create_database_engine(tmp_path / "engine.sqlite3")

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert connection.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"
    engine.dispose()


def test_session_scope_commits_successful_work(tmp_path: Path) -> None:
    database_path = tmp_path / "sessions.sqlite3"
    upgrade_database(database_path)
    engine = create_database_engine(database_path)
    factory = create_session_factory(engine)

    with session_scope(factory) as session:
        session.execute(
            text("INSERT INTO system_metadata (key, value) VALUES (:key, :value)"),
            {"key": "schema", "value": "ready"},
        )

    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT value FROM system_metadata WHERE key = 'schema'")
            ).scalar_one()
            == "ready"
        )
    engine.dispose()


def test_online_backup_is_consistent_and_readable(tmp_path: Path) -> None:
    source = tmp_path / "live" / "leave-planner.sqlite3"
    source.parent.mkdir()
    upgrade_database(source)

    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE example (value TEXT NOT NULL)")
        connection.execute("INSERT INTO example VALUES ('preserved')")

    backup = create_online_backup(
        source,
        tmp_path / "backups",
        timestamp=datetime(2026, 8, 6, 10, 30, tzinfo=UTC),
    )

    assert backup.name == "leave-planner-manual-20260806T103000Z.sqlite3"
    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT value FROM example").fetchone() == ("preserved",)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_online_backup_rejects_live_database_directory(tmp_path: Path) -> None:
    source = tmp_path / "leave-planner.sqlite3"
    source.touch()

    with pytest.raises(ValueError, match="separate"):
        create_online_backup(source, tmp_path)
