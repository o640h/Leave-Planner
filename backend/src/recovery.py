"""Operator-facing data backup and recovery API."""

from datetime import datetime
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

    return RecoveryStatus(
        data_directory=str(settings.resolved_data_dir),
        backup_directory=str(settings.backup_directory),
        backups=tuple(backup_read(backup) for backup in list_backups(settings.backup_directory)),
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
            upgrade_database(settings.database_path)
        finally:
            # Reconnect even if restore fails, so the running application is not
            # left bound to a disposed engine.
            engine = create_database_engine(settings.database_path)
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


def create_startup_backups(settings: Settings) -> None:
    """Create migration and daily safety backups before opening the database."""

    database = settings.database_path
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

    today = datetime.now().astimezone().date()
    has_today = any(
        backup.kind == "automatic" and backup.created_at.astimezone().date() == today
        for backup in list_backups(settings.backup_directory)
    )

    if not has_today:
        create_online_backup(
            database,
            settings.backup_directory,
            kind="automatic",
        )

    prune_backups(
        settings.backup_directory,
        kind="automatic",
        keep=7,
    )
