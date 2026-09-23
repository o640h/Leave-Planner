"""Atomic, restart-safe SQLite to PostgreSQL data transfer."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import URL, Connection, Engine, MetaData, Table, func, select, text
from sqlalchemy.orm import Session

from authentication.models import User
from backup import create_online_backup, verify_database
from consultant_year_summary.service import get_summary
from consultants.models import Consultant
from database import create_database_engine, database_url, sqlite_url
from leave_years.models import LeaveYear
from migrations import database_requires_upgrade, upgrade_database
from workspaces.models import Workspace, WorkspaceMembership
from workspaces.service import WorkspaceAccess, bind_workspace

IMPORT_MARKER_KEY = "sqlite_import_sha256"
IMPORT_LOCK_NAME = "leave_planner_sqlite_import"

# Parent tables precede every dependent table. Authentication and hosted workspace tables are
# deliberately absent: the destination account boundary remains authoritative.
TRANSFER_TABLES: tuple[str, ...] = (
    "holiday_calendar_versions",
    "consultants",
    "holiday_calendar_events",
    "holiday_corrections",
    "audit_events",
    "leave_years",
    "entitlement_recommendations",
    "job_plan_versions",
    "leave_bookings",
    "leave_year_adjustments",
    "public_holiday_treatments",
    "applied_entitlements",
    "job_plan_days",
    "leave_booking_days",
)


@dataclass(frozen=True)
class ImportReport:
    """Evidence returned after a completed or safely repeated import."""

    backup_path: Path
    source_sha256: str
    table_counts: Mapping[str, int]
    consultant_years: int
    already_completed: bool = False


@dataclass(frozen=True)
class _SourceSnapshot:
    sha256: str
    rows: Mapping[str, tuple[dict[str, Any], ...]]
    summaries: Mapping[tuple[int, int], str]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_foreign_keys_are_valid(path: Path) -> None:
    with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as connection:
        failures = connection.execute("PRAGMA foreign_key_check").fetchall()
    if failures:
        raise RuntimeError(f"The SQLite source contains {len(failures)} foreign-key failures")


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _canonical(item)
            for key, item in sorted(value.items())
            if key not in {"created_at", "updated_at", "recorded_at"}
        }
    if isinstance(value, list | tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


def _summary_digest(summary: Any) -> str:
    payload = _canonical(summary.model_dump(mode="python"))
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _workspace_access(session: Session) -> WorkspaceAccess:
    workspace_ids = tuple(session.scalars(select(Workspace.id).order_by(Workspace.id).limit(2)))
    if len(workspace_ids) != 1:
        raise RuntimeError("The database must contain exactly one workspace")
    return WorkspaceAccess(
        user_id=0,
        actor_label="System Import",
        workspace_id=workspace_ids[0],
        role="admin",
    )


def _summaries(engine: Engine, access: WorkspaceAccess | None = None) -> dict[tuple[int, int], str]:
    result: dict[tuple[int, int], str] = {}
    with Session(engine, expire_on_commit=False) as session:
        resolved_access = access or _workspace_access(session)
        bind_workspace(session, resolved_access)
        years = tuple(
            session.execute(
                select(LeaveYear.consultant_id, LeaveYear.id)
                .join(Consultant, Consultant.id == LeaveYear.consultant_id)
                .where(Consultant.workspace_id == resolved_access.workspace_id)
                .order_by(LeaveYear.consultant_id, LeaveYear.id)
            )
        )
        for consultant_id, leave_year_id in years:
            result[(consultant_id, leave_year_id)] = _summary_digest(
                get_summary(session, consultant_id, leave_year_id)
            )
        # Summary reads use the bundled snapshot when no synced calendar has been saved.
        session.commit()
    return result


def _reflected_tables(engine: Engine) -> dict[str, Table]:
    metadata = MetaData()
    metadata.reflect(bind=engine, only=TRANSFER_TABLES)
    missing = set(TRANSFER_TABLES) - set(metadata.tables)
    if missing:
        raise RuntimeError(f"The database is missing required tables: {', '.join(sorted(missing))}")
    return {name: metadata.tables[name] for name in TRANSFER_TABLES}


def _source_snapshot(backup: Path) -> _SourceSnapshot:
    with tempfile.TemporaryDirectory(prefix="leave-planner-import-") as directory:
        working_copy = Path(directory) / "source.sqlite3"
        shutil.copy2(backup, working_copy)
        upgrade_database(working_copy)
        _source_foreign_keys_are_valid(working_copy)

        engine = create_database_engine(sqlite_url(working_copy))
        try:
            summaries = _summaries(engine)
            tables = _reflected_tables(engine)
            with engine.connect() as connection:
                rows = {
                    name: tuple(
                        dict(row._mapping)
                        for row in connection.execute(select(table).order_by(table.c.id))
                    )
                    for name, table in tables.items()
                }
        finally:
            engine.dispose()

    return _SourceSnapshot(sha256=_sha256(backup), rows=rows, summaries=summaries)


def _target_boundary(connection: Connection) -> tuple[int, int]:
    users = connection.execute(select(User.id).order_by(User.id)).all()
    workspaces = connection.execute(select(Workspace.id).order_by(Workspace.id)).all()
    memberships = tuple(
        tuple(row)
        for row in connection.execute(
            select(WorkspaceMembership.workspace_id, WorkspaceMembership.user_id).order_by(
                WorkspaceMembership.id
            )
        )
    )
    if len(users) != 1 or len(workspaces) != 1 or memberships != ((workspaces[0][0], users[0][0]),):
        raise RuntimeError(
            "PostgreSQL must contain exactly one account, one workspace, and its membership"
        )
    return users[0][0], workspaces[0][0]


def _existing_marker(connection: Connection) -> str | None:
    marker = connection.scalar(
        text("SELECT value FROM system_metadata WHERE key = :key"),
        {"key": IMPORT_MARKER_KEY},
    )
    return marker if isinstance(marker, str) else None


def _require_empty_target(connection: Connection, tables: Mapping[str, Table]) -> None:
    occupied = {
        name: int(connection.scalar(select(func.count()).select_from(table)) or 0)
        for name, table in tables.items()
    }
    occupied = {name: count for name, count in occupied.items() if count}
    if occupied:
        details = ", ".join(f"{name}={count}" for name, count in sorted(occupied.items()))
        raise RuntimeError(f"PostgreSQL already contains application data: {details}")


def _target_rows(
    rows: tuple[dict[str, Any], ...],
    table_name: str,
    *,
    admin_id: int,
    workspace_id: int,
) -> list[dict[str, Any]]:
    result = [dict(row) for row in rows]
    if table_name in {"consultants", "holiday_corrections", "audit_events"}:
        for row in result:
            row["workspace_id"] = workspace_id
    if table_name == "audit_events":
        for row in result:
            if row.get("actor_user_id") is not None:
                row["actor_user_id"] = admin_id
    return result


def _reset_sequence(connection: Connection, table_name: str, rows: list[dict[str, Any]]) -> None:
    identifiers = [int(row["id"]) for row in rows if row.get("id") is not None]
    if not identifiers:
        return
    connection.execute(
        text("SELECT setval(pg_get_serial_sequence(:table_name, 'id'), :identifier, true)"),
        {"table_name": table_name, "identifier": max(identifiers)},
    )


def _marker_value(snapshot: _SourceSnapshot) -> str:
    return json.dumps(
        {
            "source_sha256": snapshot.sha256,
            "completed_at": datetime.now(UTC).isoformat(),
            "table_counts": {name: len(rows) for name, rows in snapshot.rows.items()},
            "consultant_years": len(snapshot.summaries),
        },
        sort_keys=True,
    )


def _marker_sha256(marker: str) -> str | None:
    try:
        value = json.loads(marker)
    except json.JSONDecodeError:
        return None
    fingerprint = value.get("source_sha256")
    return fingerprint if isinstance(fingerprint, str) else None


def import_sqlite_database(
    source: Path,
    target: str | URL,
    *,
    backup_directory: Path | None = None,
) -> ImportReport:
    """Back up and atomically transfer one SQLite database into an empty PostgreSQL workspace."""

    source_path = source.expanduser().resolve()
    verify_database(source_path)
    destination_directory = (
        backup_directory.expanduser().resolve()
        if backup_directory is not None
        else source_path.parent / "leave-planner-import-backups"
    )
    backup = create_online_backup(source_path, destination_directory, kind="manual")
    snapshot = _source_snapshot(backup)

    target_url = database_url(target)
    if target_url.get_backend_name() != "postgresql":
        raise ValueError("The import destination must use postgresql+psycopg")
    if database_requires_upgrade(target_url):
        raise RuntimeError("PostgreSQL must be migrated to the current schema before import")

    engine = create_database_engine(target_url)
    try:
        target_tables = _reflected_tables(engine)
        with engine.begin() as connection:
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:name))"),
                {"name": IMPORT_LOCK_NAME},
            )
            marker = _existing_marker(connection)
            if marker is not None:
                if _marker_sha256(marker) != snapshot.sha256:
                    raise RuntimeError("A different SQLite database has already been imported")
                return ImportReport(
                    backup_path=backup,
                    source_sha256=snapshot.sha256,
                    table_counts={name: len(rows) for name, rows in snapshot.rows.items()},
                    consultant_years=len(snapshot.summaries),
                    already_completed=True,
                )

            admin_id, workspace_id = _target_boundary(connection)
            _require_empty_target(connection, target_tables)

            for table_name in TRANSFER_TABLES:
                rows = _target_rows(
                    snapshot.rows[table_name],
                    table_name,
                    admin_id=admin_id,
                    workspace_id=workspace_id,
                )
                if rows:
                    connection.execute(target_tables[table_name].insert(), rows)
                _reset_sequence(connection, table_name, rows)

            target_access = WorkspaceAccess(
                user_id=admin_id,
                actor_label="System Import",
                workspace_id=workspace_id,
                role="admin",
            )
            with Session(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as session:
                bind_workspace(session, target_access)
                target_summaries = {
                    (consultant_id, leave_year_id): _summary_digest(
                        get_summary(session, consultant_id, leave_year_id)
                    )
                    for consultant_id, leave_year_id in sorted(snapshot.summaries)
                }
                session.commit()
            if target_summaries != snapshot.summaries:
                differing = sorted(set(target_summaries) | set(snapshot.summaries))
                raise RuntimeError(
                    "PostgreSQL consultant-year reconciliation failed for "
                    + ", ".join(
                        f"{consultant_id}/{year_id}" for consultant_id, year_id in differing
                    )
                )

            target_counts = {
                name: int(connection.scalar(select(func.count()).select_from(table)) or 0)
                for name, table in target_tables.items()
            }
            source_counts = {name: len(rows) for name, rows in snapshot.rows.items()}
            if target_counts != source_counts:
                raise RuntimeError("PostgreSQL table-count reconciliation failed")

            connection.execute(
                text("INSERT INTO system_metadata (key, value) VALUES (:key, :value)"),
                {"key": IMPORT_MARKER_KEY, "value": _marker_value(snapshot)},
            )

        return ImportReport(
            backup_path=backup,
            source_sha256=snapshot.sha256,
            table_counts={name: len(rows) for name, rows in snapshot.rows.items()},
            consultant_years=len(snapshot.summaries),
        )
    finally:
        engine.dispose()
