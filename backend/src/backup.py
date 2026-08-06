"""Verified online SQLite backup operations."""

import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path


def create_online_backup(
    database_path: Path,
    backup_directory: Path,
    *,
    timestamp: datetime | None = None,
) -> Path:
    """Create a consistent SQLite backup without stopping the application."""
    source = database_path.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Database does not exist: {source}")

    destination_dir = backup_directory.expanduser().resolve()
    if destination_dir == source.parent:
        raise ValueError("Backup directory must be separate from the live database directory")
    destination_dir.mkdir(parents=True, exist_ok=True)

    moment = timestamp or datetime.now(UTC)
    destination = destination_dir / f"leave-planner-{moment:%Y%m%dT%H%M%SZ}.sqlite3"
    temporary = destination.with_suffix(".sqlite3.tmp")

    try:
        with (
            closing(sqlite3.connect(source)) as source_connection,
            closing(sqlite3.connect(temporary)) as destination_connection,
        ):
            source_connection.backup(destination_connection)
            result = destination_connection.execute("PRAGMA integrity_check").fetchone()
            if result != ("ok",):
                raise RuntimeError("SQLite backup integrity check failed")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)

    return destination
