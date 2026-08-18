"""Verified SQLite backup and restore operations."""

import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

BackupKind = Literal["manual", "automatic", "pre-migration", "pre-restore"]

REQUIRED_TABLES = {
    "alembic_version",
    "system_metadata",
}


@dataclass(frozen=True)
class BackupFile:
    """One verified backup available to the operator."""

    name: str
    kind: BackupKind
    created_at: datetime
    size_bytes: int


def verify_database(database_path: Path) -> None:
    """Reject damaged files and files that are not Leave Planner databases."""

    path = database_path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Database does not exist: {path}")

    try:
        with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            if result != ("ok",):
                raise RuntimeError("SQLite integrity check failed")

            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
    except sqlite3.DatabaseError as error:
        raise RuntimeError("The selected file is not a readable SQLite database") from error

    if not tables >= REQUIRED_TABLES:
        raise RuntimeError("The selected file is not a Leave Planner backup")


def create_online_backup(
    database_path: Path,
    backup_directory: Path,
    *,
    kind: BackupKind = "manual",
    timestamp: datetime | None = None,
) -> Path:
    """Create and verify a consistent backup while the application is running."""

    source = database_path.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Database does not exist: {source}")

    destination_dir = backup_directory.expanduser().resolve()
    if destination_dir == source.parent:
        raise ValueError("Backup directory must be separate from the live database directory")

    destination_dir.mkdir(parents=True, exist_ok=True)

    moment = timestamp or datetime.now(UTC)
    destination = destination_dir / f"leave-planner-{kind}-{moment:%Y%m%dT%H%M%SZ}.sqlite3"
    temporary = destination.with_suffix(".sqlite3.tmp")

    try:
        with (
            closing(sqlite3.connect(source)) as source_connection,
            closing(sqlite3.connect(temporary)) as destination_connection,
        ):
            source_connection.backup(destination_connection)

        verify_database(temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)

    return destination


def backup_kind(path: Path) -> BackupKind | None:
    """Read the managed backup type from its filename."""

    for kind in ("manual", "automatic", "pre-migration", "pre-restore"):
        if path.name.startswith(f"leave-planner-{kind}-"):
            return kind

    return None


def backup_created_at(path: Path, kind: BackupKind) -> datetime:
    """Read the immutable UTC creation time encoded in a managed filename."""

    prefix = f"leave-planner-{kind}-"
    timestamp = path.name.removeprefix(prefix).removesuffix(".sqlite3")
    try:
        return datetime.strptime(timestamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        return datetime.fromtimestamp(path.stat().st_mtime, UTC)


def list_backups(backup_directory: Path) -> tuple[BackupFile, ...]:
    """List managed backups from newest to oldest."""

    directory = backup_directory.expanduser().resolve()
    if not directory.is_dir():
        return ()

    backups: list[BackupFile] = []

    for path in directory.glob("leave-planner-*.sqlite3"):
        kind = backup_kind(path)
        if kind is None:
            continue

        details = path.stat()
        backups.append(
            BackupFile(
                name=path.name,
                kind=kind,
                created_at=backup_created_at(path, kind),
                size_bytes=details.st_size,
            )
        )

    return tuple(sorted(backups, key=lambda item: item.created_at, reverse=True))


def resolve_backup(backup_directory: Path, backup_name: str) -> Path:
    """Resolve a backup name without permitting paths outside the backup directory."""

    directory = backup_directory.expanduser().resolve()

    if Path(backup_name).name != backup_name:
        raise ValueError("Backup name must not contain a directory")

    backup = (directory / backup_name).resolve()

    if backup.parent != directory:
        raise ValueError("Backup must be inside the managed backup directory")

    if backup_kind(backup) is None:
        raise ValueError("The selected file is not a managed Leave Planner backup")

    verify_database(backup)
    return backup


def restore_database(backup_path: Path, database_path: Path) -> None:
    """Replace the live database with a verified backup."""

    source = backup_path.expanduser().resolve()
    destination = database_path.expanduser().resolve()
    temporary = destination.with_suffix(".sqlite3.restore")

    verify_database(source)
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        with (
            closing(sqlite3.connect(source)) as source_connection,
            closing(sqlite3.connect(temporary)) as destination_connection,
        ):
            source_connection.backup(destination_connection)

        verify_database(temporary)
        os.replace(temporary, destination)

        # These files belong to the previous live database generation.
        destination.with_name(f"{destination.name}-wal").unlink(missing_ok=True)
        destination.with_name(f"{destination.name}-shm").unlink(missing_ok=True)
    finally:
        temporary.unlink(missing_ok=True)


def prune_backups(
    backup_directory: Path,
    *,
    kind: BackupKind,
    keep: int,
) -> None:
    """Retain only the newest managed backups of one type."""

    matching = [backup for backup in list_backups(backup_directory) if backup.kind == kind]

    for backup in matching[keep:]:
        (backup_directory / backup.name).unlink(missing_ok=True)
