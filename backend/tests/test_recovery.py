"""Verified backup and restore tests using the real API and database."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backup import list_backups, prune_backups, resolve_backup, verify_database
from main import create_app
from migrations import alembic_config, upgrade_database
from recovery import create_startup_backups
from settings import Settings

pytestmark = pytest.mark.sqlite_only


def app_for(data_dir: Path) -> FastAPI:
    return create_app(
        settings=Settings(environment="test", data_dir=data_dir, authentication_required=False),
        frontend_dist=data_dir / "no-frontend-build",
    )


def job_plan() -> dict[str, Any]:
    """Return a simple 10-PA working pattern covering the complete year."""

    return {
        "effective_from": "2026-01-01",
        "effective_until": "2027-01-01",
        "cycle_anchor_date": None,
        "week_count": 1,
        "contracted_pas": "10",
        "dcc_pas": "8",
        "spa_pas": "2",
        "other_pas": "0",
        "hours_per_pa": "4",
        "reconciliation_override_reason": None,
        "days": [
            {
                "cycle_week": 1,
                "weekday": weekday,
                "dcc_hours": "6.4" if weekday < 5 else "0",
                "spa_hours": "1.6" if weekday < 5 else "0",
                "other_hours": "0",
            }
            for weekday in range(7)
        ],
    }


def test_restore_recovers_the_complete_consultant_year(tmp_path: Path) -> None:
    """A verified backup must recover inputs, snapshots, balances, and audit history."""

    with TestClient(app_for(tmp_path)) as client:
        consultant = client.post(
            "/api/consultants",
            json={"name": "Recovery Example", "post_title": "Consultant"},
        ).json()
        consultant_id = int(consultant["id"])
        year = client.post(
            f"/api/consultants/{consultant_id}/leave-years",
            json={"start_date": "2026-01-01", "end_date": "2026-12-31"},
        ).json()
        year_id = int(year["id"])
        root = f"/api/consultants/{consultant_id}/leave-years/{year_id}"

        assert client.post(f"{root}/job-plans", json=job_plan()).status_code == 201
        assert (
            client.put(
                f"{root}/entitlement",
                json={
                    "mode": "manual",
                    "dcc_hours": "240",
                    "spa_hours": "60",
                    "other_hours": "0",
                    "reason": "Recovery reference values",
                },
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"{root}/bookings",
                json={
                    "start_date": "2026-02-02",
                    "end_date": "2026-02-02",
                    "state": "taken",
                    "note": "Recovery reference booking",
                    "overrides": [],
                },
            ).status_code
            == 201
        )

        expected_summary = client.get(f"{root}/summary").json()
        assert client.post("/api/settings/recovery/backups").status_code == 200
        status = client.get("/api/settings/recovery").json()
        backup_name = next(
            backup["name"] for backup in status["backups"] if backup["kind"] == "manual"
        )

        # Change durable data after the backup so the restore has something real to reverse.
        assert (
            client.put(
                f"/api/consultants/{consultant_id}",
                json={"name": "Changed After Backup", "post_title": "Consultant"},
            ).status_code
            == 200
        )
        assert client.get(f"{root}/summary").json() != expected_summary

        restored = client.post(
            "/api/settings/recovery/restore",
            json={"backup_name": backup_name, "confirmation": "RESTORE"},
        )
        assert restored.status_code == 200, restored.text
        assert client.get(f"{root}/summary").json() == expected_summary


def test_restore_only_accepts_managed_backup_names(tmp_path: Path) -> None:
    backup_directory = tmp_path / "backups"

    with pytest.raises(ValueError, match="directory"):
        resolve_backup(backup_directory, "../leave-planner-manual-example.sqlite3")


def test_automatic_retention_does_not_remove_manual_backups(tmp_path: Path) -> None:
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()

    for month in range(1, 13):
        (
            backup_directory / f"leave-planner-automatic-2025{month:02d}01T120000Z.sqlite3"
        ).write_bytes(b"automatic")
    manual = backup_directory / "leave-planner-manual-20260115T120000Z.sqlite3"
    manual.write_bytes(b"manual")

    prune_backups(backup_directory, kind="automatic", keep=10)

    automatic = tuple(backup_directory.glob("leave-planner-automatic-*.sqlite3"))
    assert len(automatic) == 10
    assert not (backup_directory / "leave-planner-automatic-20250101T120000Z.sqlite3").exists()
    assert not (backup_directory / "leave-planner-automatic-20250201T120000Z.sqlite3").exists()
    assert manual.is_file()


def test_startup_creates_one_verified_automatic_backup_per_calendar_month(
    tmp_path: Path,
) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.database_path)

    create_startup_backups(settings, now=datetime(2026, 8, 1, 8, 0, tzinfo=UTC))
    create_startup_backups(settings, now=datetime(2026, 8, 31, 18, 0, tzinfo=UTC))

    august_backups = [
        backup for backup in list_backups(settings.backup_directory) if backup.kind == "automatic"
    ]
    assert len(august_backups) == 1

    create_startup_backups(settings, now=datetime(2026, 9, 1, 8, 0, tzinfo=UTC))

    automatic_backups = [
        backup for backup in list_backups(settings.backup_directory) if backup.kind == "automatic"
    ]
    assert len(automatic_backups) == 2
    assert automatic_backups[0].created_at == datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
    for backup in automatic_backups:
        verify_database(settings.backup_directory / backup.name)

    with TestClient(app_for(tmp_path)) as client:
        status = client.get("/api/settings/recovery").json()

    assert status["latest_automatic_backup_at"] == "2026-09-01T08:00:00Z"


def test_startup_protects_a_database_before_migration(tmp_path: Path) -> None:
    """An older schema receives both migration and monthly safety copies before startup."""

    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.database_path)
    command.downgrade(alembic_config(settings.database_path), "-1")

    create_startup_backups(settings)

    kinds = {backup.kind for backup in list_backups(settings.backup_directory)}
    assert kinds == {"automatic", "pre-migration"}
