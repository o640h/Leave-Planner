"""Operator-facing data backup and recovery API."""

from datetime import UTC, datetime
from typing import Literal, cast

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from backup import (
    BackupFile,
    create_online_backup,
    list_backups,
    prune_backups,
    resolve_backup,
    restore_database,
)
from database import create_database_engine, create_session_factory
from errors import ApiError
from migrations import upgrade_database
from settings import Settings

router = APIRouter(prefix="/api/settings/recovery", tags=["recovery"])


class BackupRead(BaseModel):
    name: str
    kind: Literal["manual", "automatic", "pre-migration", "pre-restore"]
    created_at: datetime
    size_bytes: int


class RecoveryStatus(BaseModel):
    data_directory: str
    backup_directory: str
    latest_automatic_backup_at: datetime | None
    backups: tuple[BackupRead, ...]


class RestoreCommand(BaseModel):
    backup_name: str = Field(min_length=1, max_length=255)
    confirmation: str


class RecoveryResult(BaseModel):
    message: str


def backup_read(backup: BackupFile) -> BackupRead:
    return BackupRead(
        name=backup.name,
        kind=backup.kind,
        created_at=backup.created_at,
        size_bytes=backup.size_bytes,
    )


def runtime_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


@router.get("", response_model=RecoveryStatus)
def recovery_status(request: Request) -> RecoveryStatus:
    """Return local storage information and available backups."""

    settings = runtime_settings(request)
    backups = list_backups(settings.backup_directory)
    latest_automatic = next((backup for backup in backups if backup.kind == "automatic"), None)

    return RecoveryStatus(
        data_directory=str(settings.resolved_data_dir),
        backup_directory=str(settings.backup_directory),
        latest_automatic_backup_at=(
            latest_automatic.created_at if latest_automatic is not None else None
        ),
        backups=tuple(backup_read(backup) for backup in backups),
    )


@router.post("/backups", response_model=RecoveryResult)
def create_manual_backup(request: Request) -> RecoveryResult:
    """Create an operator-requested verified backup."""

    settings = runtime_settings(request)

    try:
        backup = create_online_backup(
            settings.database_path,
            settings.backup_directory,
            kind="manual",
        )
    except (OSError, RuntimeError, ValueError) as error:
        raise ApiError(
            status_code=500,
            code="backup_failed",
            message="The backup could not be created.",
            details=str(error),
        ) from error

    return RecoveryResult(message=f"{backup.name} was created and verified.")


@router.post("/restore", response_model=RecoveryResult)
def restore_backup(
    command: RestoreCommand,
    request: Request,
) -> RecoveryResult:
    """Restore a managed backup and rebuild the application database connection."""

    if command.confirmation != "RESTORE":
        raise ApiError(
            status_code=422,
            code="restore_confirmation_required",
            message="Type RESTORE to confirm.",
        )

    settings = runtime_settings(request)

    try:
        selected_backup = resolve_backup(
            settings.backup_directory,
            command.backup_name,
        )

        # Always preserve the current state before replacing it.
        create_online_backup(
            settings.database_path,
            settings.backup_directory,
            kind="pre-restore",
        )

        request.app.state.database_engine.dispose()
        try:
            restore_database(selected_backup, settings.database_path)
            upgrade_database(settings.resolved_database_url)
        finally:
            # Reconnect even if restore fails, so the running application is not
            # left bound to a disposed engine.
            engine = create_database_engine(settings.resolved_database_url)
            request.app.state.database_engine = engine
            request.app.state.session_factory = create_session_factory(engine)

        prune_backups(
            settings.backup_directory,
            kind="pre-restore",
            keep=3,
        )
    except (OSError, RuntimeError, ValueError) as error:
        raise ApiError(
            status_code=400,
            code="restore_failed",
            message="The selected backup could not be restored.",
            details=str(error),
        ) from error

    return RecoveryResult(message="The backup was restored. Leave Planner will now reload.")


def create_startup_backups(settings: Settings, *, now: datetime | None = None) -> None:
    """Create migration and monthly safety backups before opening the database."""

    database = settings.sqlite_database_path
    if database is None:
        return
    if not database.is_file():
        return

    from migrations import database_requires_upgrade

    if database_requires_upgrade(database):
        create_online_backup(
            database,
            settings.backup_directory,
            kind="pre-migration",
        )
        prune_backups(
            settings.backup_directory,
            kind="pre-migration",
            keep=3,
        )

    moment = (now or datetime.now(UTC)).astimezone()

    automatic_backups = tuple(
        backup
        for backup in list_backups(settings.backup_directory)
        if backup.kind == "automatic"
    )
    has_current_month = any(
        (local_created := backup.created_at.astimezone()).year == moment.year
        and local_created.month == moment.month
        for backup in automatic_backups
    )

    if not has_current_month:
        # Creation includes an integrity and schema check. Retention runs only after
        # that verified copy has been moved into place.
        create_online_backup(
            database,
            settings.backup_directory,
            kind="automatic",
            timestamp=moment.astimezone(UTC),
        )

    prune_backups(
        settings.backup_directory,
        kind="automatic",
        keep=10,
    )
