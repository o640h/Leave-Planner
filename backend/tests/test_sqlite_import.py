"""Verified SQLite to PostgreSQL transfer of the workbook-shaped dataset."""

import os
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from pypdf import PdfReader
from reference_cases.workbook import WORKBOOK_LEAVE_ROWS

from authentication.service import create_account
from database import create_database_engine, create_session_factory, database_url, session_scope
from database_transfer import import_sqlite_database
from main import create_app
from migrations import upgrade_database
from settings import Settings
from workspaces.models import ADMIN_ROLE, Workspace, WorkspaceMembership

POSTGRES_TEST_URL = os.environ.get("LEAVE_PLANNER_TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="Set LEAVE_PLANNER_TEST_POSTGRES_URL to run PostgreSQL import checks",
)


def _job_plan(effective_from: str, effective_until: str) -> dict[str, Any]:
    visible = {0: ("8", "0.5"), 1: ("8", "2"), 2: ("4.5", "1.5")}
    return {
        "effective_from": effective_from,
        "effective_until": effective_until,
        "cycle_anchor_date": None,
        "week_count": 1,
        "contracted_pas": "8.47",
        "dcc_pas": "5.91",
        "spa_pas": "2.56",
        "other_pas": "0",
        "hours_per_pa": "4",
        "reconciliation_override_reason": None,
        "days": [
            {
                "cycle_week": 1,
                "weekday": weekday,
                "dcc_hours": visible.get(weekday, ("0", "0"))[0],
                "spa_hours": visible.get(weekday, ("0", "0"))[1],
                "other_hours": "0",
            }
            for weekday in range(7)
        ],
    }


def _synthetic_job_plan(
    effective_from: str,
    effective_until: str,
    *,
    contracted_pas: str,
    dcc_pas: str,
    spa_pas: str,
    week_count: int,
    pattern: dict[tuple[int, int], tuple[str, str]],
) -> dict[str, Any]:
    return {
        "effective_from": effective_from,
        "effective_until": effective_until,
        "cycle_anchor_date": "2025-12-29" if week_count > 1 else None,
        "week_count": week_count,
        "contracted_pas": contracted_pas,
        "dcc_pas": dcc_pas,
        "spa_pas": spa_pas,
        "other_pas": "0",
        "hours_per_pa": "4",
        "reconciliation_override_reason": None,
        "days": [
            {
                "cycle_week": week,
                "weekday": weekday,
                "dcc_hours": pattern.get((week, weekday), ("0", "0"))[0],
                "spa_hours": pattern.get((week, weekday), ("0", "0"))[1],
                "other_hours": "0",
            }
            for week in range(1, week_count + 1)
            for weekday in range(7)
        ],
    }


def _add_synthetic_sources(client: TestClient) -> None:
    cases = (
        (
            "Full Time",
            (
                _synthetic_job_plan(
                    "2026-01-01",
                    "2027-01-01",
                    contracted_pas="10",
                    dcc_pas="8",
                    spa_pas="2",
                    week_count=1,
                    pattern={(1, weekday): ("8", "0") for weekday in range(5)},
                ),
            ),
        ),
        (
            "LTFT Uneven",
            (
                _synthetic_job_plan(
                    "2026-01-01",
                    "2027-01-01",
                    contracted_pas="6",
                    dcc_pas="4.5",
                    spa_pas="1.5",
                    week_count=1,
                    pattern={(1, 0): ("12", "0"), (1, 1): ("6", "6")},
                ),
            ),
        ),
        (
            "Capped Multiweek",
            (
                _synthetic_job_plan(
                    "2026-01-01",
                    "2026-10-01",
                    contracted_pas="12",
                    dcc_pas="9",
                    spa_pas="3",
                    week_count=2,
                    pattern={(1, 0): ("8", "4"), (2, 0): ("12", "0")},
                ),
                _synthetic_job_plan(
                    "2026-10-01",
                    "2027-01-01",
                    contracted_pas="12",
                    dcc_pas="8",
                    spa_pas="4",
                    week_count=2,
                    pattern={(1, 3): ("8", "4"), (2, 3): ("12", "0")},
                ),
            ),
        ),
    )
    for name, plans in cases:
        consultant_id = client.post(
            "/api/consultants", json={"name": name, "post_title": "Consultant"}
        ).json()["id"]
        leave_year_id = client.post(
            f"/api/consultants/{consultant_id}/leave-years",
            json={"start_date": "2026-01-01", "end_date": "2026-12-31"},
        ).json()["id"]
        root = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}"
        for plan in plans:
            assert client.post(f"{root}/job-plans", json=plan).status_code == 201
        assert (
            client.put(
                f"{root}/entitlement",
                json={"mode": "calculated", "seven_years_or_more": False, "other_hours": "0"},
            ).status_code
            == 200
        )


def _create_workbook_source(data_dir: Path) -> tuple[Path, int, int]:
    settings = Settings(
        environment="test",
        data_dir=data_dir,
        database_url=None,
        authentication_required=False,
    )
    app = create_app(settings=settings, frontend_dist=data_dir / "missing-frontend")
    with TestClient(app) as client:
        consultant_id = int(
            client.post(
                "/api/consultants",
                json={"name": "Anonymous", "post_title": "Consultant in Radiology"},
            ).json()["id"]
        )
        leave_year_id = int(
            client.post(
                f"/api/consultants/{consultant_id}/leave-years",
                json={"start_date": "2025-08-29", "end_date": "2026-08-28"},
            ).json()["id"]
        )
        root = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}"
        assert (
            client.post(f"{root}/job-plans", json=_job_plan("2025-08-29", "2026-08-01")).status_code
            == 201
        )
        assert (
            client.post(f"{root}/job-plans", json=_job_plan("2026-08-01", "2026-08-29")).status_code
            == 201
        )
        assert (
            client.put(
                f"{root}/entitlement",
                json={"mode": "calculated", "seven_years_or_more": True, "other_hours": "0"},
            ).status_code
            == 200
        )
        assert (
            client.put(
                f"{root}/carry-forward",
                json={"dcc_hours": "41.25", "spa_hours": "0"},
            ).status_code
            == 200
        )
        assert (
            client.put(
                f"{root}/public-holidays/2026-05-04/treatment",
                json={"basis": "qualifying_on_call", "note": "Workbook on-call entry"},
            ).status_code
            == 200
        )

        for leave_date, dcc, spa in WORKBOOK_LEAVE_ROWS:
            iso_date = leave_date.isoformat()
            assert (
                client.post(
                    f"{root}/bookings",
                    json={
                        "start_date": iso_date,
                        "end_date": iso_date,
                        "state": "taken",
                        "note": "Workbook reference",
                        "overrides": [{"leave_date": iso_date, "dcc_hours": dcc, "spa_hours": spa}],
                    },
                ).status_code
                == 201
            )

        _add_synthetic_sources(client)

    return settings.database_path, consultant_id, leave_year_id


def _prepare_target(url: str) -> None:
    target = database_url(url)
    upgrade_database(target)
    engine = create_database_engine(target)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            account = create_account(
                session,
                display_name="Import Operator",
                email="import@example.org",
                password="ImportTestPassword!",
                verified_at=datetime.now(UTC),
            )
            workspace = session.get(Workspace, 1)
            assert workspace is not None
            session.add(
                WorkspaceMembership(
                    workspace_id=workspace.id,
                    user_id=account.id,
                    role=ADMIN_ROLE,
                )
            )
            account.last_workspace_id = workspace.id
    finally:
        engine.dispose()


def test_workbook_database_import_reconciles_and_is_restart_safe(tmp_path: Path) -> None:
    assert POSTGRES_TEST_URL is not None
    source, consultant_id, leave_year_id = _create_workbook_source(tmp_path / "source")
    _prepare_target(POSTGRES_TEST_URL)

    report = import_sqlite_database(
        source,
        POSTGRES_TEST_URL,
        backup_directory=tmp_path / "verified-backups",
    )
    repeated = import_sqlite_database(
        source,
        POSTGRES_TEST_URL,
        backup_directory=tmp_path / "verified-backups",
    )

    assert report.already_completed is False
    assert repeated.already_completed is True
    assert report.source_sha256 == repeated.source_sha256
    assert report.consultant_years == 4
    assert report.table_counts["leave_bookings"] == len(WORKBOOK_LEAVE_ROWS)
    assert report.backup_path.is_file()

    app = create_app(
        settings=Settings(
            environment="test",
            database_url=SecretStr(POSTGRES_TEST_URL),
            authentication_required=False,
        ),
        frontend_dist=tmp_path / "missing-frontend",
    )
    root = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}"
    with TestClient(app) as client:
        summary_response = client.get(f"{root}/summary")
        pdf_response = client.get(f"{root}/leave-log.pdf")

    assert summary_response.status_code == 200
    summary = summary_response.json()
    actual = summary["balances"]["actual"]
    assert Decimal(summary["entitlement"]["application"]["entitlement"]["dcc_hours"]) == Decimal(
        "203.304"
    )
    assert Decimal(summary["entitlement"]["application"]["entitlement"]["spa_hours"]) == Decimal(
        "88.064"
    )
    assert Decimal(summary["carry_forward"]["dcc_hours"]) == Decimal("41.25")
    assert Decimal(summary["carry_forward"]["spa_hours"]) == Decimal("0")
    assert Decimal(actual["used"]["dcc_hours"]) == Decimal("229.5")
    assert Decimal(actual["used"]["spa_hours"]) == Decimal("18")
    assert Decimal(actual["remaining"]["dcc_hours"]).quantize(Decimal("0.001")) == Decimal("15.054")
    assert Decimal(actual["remaining"]["spa_hours"]).quantize(Decimal("0.001")) == Decimal("70.064")
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    exported_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(pdf_response.content)).pages
    )
    assert "229.5h" in exported_text
    assert "18h" in exported_text
    assert "15.05h" in exported_text
    assert "70.06h" in exported_text
