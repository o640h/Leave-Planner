"""Database migration and online backup smoke tests."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import inspect, text

from backup import create_online_backup
from database import create_database_engine, create_session_factory, session_scope, sqlite_url
from database_transfer.service import _source_foreign_keys_are_valid
from migrations import (
    DatabaseUpgradeRequired,
    alembic_config,
    require_database_current,
    upgrade_database,
)


def test_alembic_upgrade_creates_foundation_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "migrated.sqlite3"

    upgrade_database(database_path)

    engine = create_database_engine(sqlite_url(database_path))
    assert {
        "alembic_version",
        "system_metadata",
        "consultants",
        "leave_years",
        "audit_events",
        "users",
        "user_sessions",
        "security_events",
        "job_plan_versions",
        "job_plan_days",
    } <= set(inspect(engine).get_table_names())
    job_plan_columns = {
        column["name"] for column in inspect(engine).get_columns("job_plan_versions")
    }
    booking_day_columns = {
        column["name"] for column in inspect(engine).get_columns("leave_booking_days")
    }
    holiday_treatment_columns = {
        column["name"] for column in inspect(engine).get_columns("public_holiday_treatments")
    }
    assert {"contracted_pas", "deduction_factor"} <= booking_day_columns
    assert "additional_dcc_hours" not in job_plan_columns
    assert "additional_spa_hours" not in job_plan_columns
    assert "worked_date" not in holiday_treatment_columns
    engine.dispose()


def test_current_schema_check_requires_explicit_upgrade(tmp_path: Path) -> None:
    database_path = tmp_path / "unmigrated.sqlite3"
    database_path.touch()

    with pytest.raises(DatabaseUpgradeRequired, match="explicit migration command"):
        require_database_current(database_path)

    upgrade_database(database_path)

    require_database_current(database_path)


def test_sqlite_engine_enables_integrity_pragmas(tmp_path: Path) -> None:
    engine = create_database_engine(sqlite_url(tmp_path / "engine.sqlite3"))

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert connection.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"
    engine.dispose()


def test_import_foreign_key_check_closes_its_read_only_connection(tmp_path: Path) -> None:
    database_path = tmp_path / "import-source.sqlite3"
    upgrade_database(database_path)

    # The restart-safety proof validates the same source twice. Python 3.14 reports an
    # unclosed sqlite3 connection as an error when either validation reaches finalization.
    _source_foreign_keys_are_valid(database_path)
    _source_foreign_keys_are_valid(database_path)


def test_deduction_migration_backfills_existing_booking_days(tmp_path: Path) -> None:
    database_path = tmp_path / "existing-booking.sqlite3"
    config = alembic_config(database_path)
    command.upgrade(config, "0009")

    with closing(sqlite3.connect(database_path)) as connection, connection:
        connection.execute("INSERT INTO consultants (id, name) VALUES (1, 'Consultant')")
        connection.execute(
            """
            INSERT INTO leave_years (id, consultant_id, start_date, end_date)
            VALUES (1, 1, '2025-08-29', '2026-08-28')
            """
        )
        connection.execute(
            """
            INSERT INTO job_plan_versions (
                id, leave_year_id, effective_from, effective_until, cycle_anchor_date,
                week_count, contracted_pas, dcc_pas, spa_pas, other_pas, hours_per_pa
            ) VALUES (
                1, 1, '2025-08-29', '2026-08-29', '2025-08-25',
                1, 12, 9, 3, 0, 4
            )
            """
        )
        connection.execute(
            """
            INSERT INTO leave_bookings (
                id, leave_year_id, start_date, end_date, state
            ) VALUES (1, 1, '2025-10-20', '2025-10-20', 'taken')
            """
        )
        connection.execute(
            """
            INSERT INTO leave_booking_days (
                booking_id, job_plan_id, leave_date,
                standard_dcc_hours, standard_spa_hours, standard_other_hours,
                deduction_dcc_hours, deduction_spa_hours, deduction_other_hours
            ) VALUES (
                1, 1, '2025-10-20', 8, 0.5, 0, 8, 0.5, 0
            )
            """
        )

    command.upgrade(config, "head")

    with closing(sqlite3.connect(database_path)) as connection, connection:
        contracted_pas, deduction_factor = connection.execute(
            "SELECT contracted_pas, deduction_factor FROM leave_booking_days"
        ).fetchone()

    assert contracted_pas == 12
    assert Decimal(deduction_factor) == Decimal("10") / Decimal("12")


def test_session_scope_commits_successful_work(tmp_path: Path) -> None:
    database_path = tmp_path / "sessions.sqlite3"
    upgrade_database(database_path)
    engine = create_database_engine(sqlite_url(database_path))
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


def test_postgresql_alembic_configuration_preserves_the_driver_and_credentials() -> None:
    url = "postgresql+psycopg://leave_planner:p%40ss@database:5432/leave_planner"

    configured = alembic_config(url).get_main_option("sqlalchemy.url")

    assert configured == url


def test_online_backup_is_consistent_and_readable(tmp_path: Path) -> None:
    source = tmp_path / "live" / "leave-planner.sqlite3"
    source.parent.mkdir()
    upgrade_database(source)

    with closing(sqlite3.connect(source)) as connection, connection:
        connection.execute("CREATE TABLE example (value TEXT NOT NULL)")
        connection.execute("INSERT INTO example VALUES ('preserved')")

    backup = create_online_backup(
        source,
        tmp_path / "backups",
        timestamp=datetime(2026, 8, 6, 10, 30, tzinfo=UTC),
    )

    assert backup.name == "leave-planner-manual-20260806T103000Z.sqlite3"
    with closing(sqlite3.connect(backup)) as connection, connection:
        assert connection.execute("SELECT value FROM example").fetchone() == ("preserved",)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_online_backup_rejects_live_database_directory(tmp_path: Path) -> None:
    source = tmp_path / "leave-planner.sqlite3"
    source.touch()

    with pytest.raises(ValueError, match="separate"):
        create_online_backup(source, tmp_path)
