"""Operator-level API tests for job-plan setup and preview."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from main import create_app
from settings import Settings


def app_for(data_dir: Path) -> FastAPI:
    """Run the real API and migrations against an isolated SQLite database."""

    return create_app(
        settings=Settings(environment="test", data_dir=data_dir),
        frontend_dist=data_dir / "no-frontend-build",
    )


def setup_leave_year(client: TestClient) -> tuple[int, int]:
    consultant = client.post(
        "/api/consultants",
        json={"name": "Dr Alex Morgan", "post_title": "Consultant in Radiology"},
    ).json()
    leave_year = client.post(
        f"/api/consultants/{consultant['id']}/leave-years",
        json={"start_date": "2025-08-29", "end_date": "2026-08-28"},
    ).json()
    return int(consultant["id"]), int(leave_year["id"])


def workbook_job_plan() -> dict[str, Any]:
    """Return the workbook's one-week PA split and visible weekday pattern."""

    visible_hours = {
        0: ("8", "0.5"),
        1: ("8", "2"),
        2: ("4.5", "1.5"),
    }
    days = []
    for weekday in range(7):
        dcc, spa = visible_hours.get(weekday, ("0", "0"))
        days.append(
            {
                "cycle_week": 1,
                "weekday": weekday,
                "dcc_hours": dcc,
                "spa_hours": spa,
                "other_hours": "0",
            }
        )

    return {
        "effective_from": "2025-08-29",
        "effective_until": "2026-08-29",
        "cycle_anchor_date": None,
        "week_count": 1,
        "contracted_pas": "8.470",
        "dcc_pas": "5.910",
        "spa_pas": "2.560",
        "other_pas": "0",
        "hours_per_pa": "4",
        "additional_dcc_hours": "3",
        "additional_spa_hours": "4",
        "reconciliation_override_reason": None,
        "days": days,
    }


def test_preview_save_edit_restart_and_audit_job_plan(tmp_path: Path) -> None:
    details = workbook_job_plan()

    with TestClient(app_for(tmp_path)) as client:
        consultant_id, leave_year_id = setup_leave_year(client)
        path = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/job-plans"

        # Preview proves the API uses the existing pure job-plan calculations before saving.
        preview = client.post(f"{path}/preview", json=details)
        assert preview.status_code == 200
        assert preview.json()["is_reconciled"] is True
        assert preview.json()["average_visible_hours"] == "24.5"
        # The workbook adds flexible work to its standard weekly totals, but
        # the dated weekday grid remains the source of leave deductions.
        assert preview.json()["average_standard_dcc_hours"] == "23.5"
        assert preview.json()["average_standard_spa_hours"] == "8.0"
        assert preview.json()["average_standard_hours"] == "31.5"

        created = client.post(path, json=details)
        assert created.status_code == 201
        job_plan_id = created.json()["id"]

        # A full replacement edit keeps the weekday grid and audit history together.
        changed = workbook_job_plan()
        changed["days"] = [dict(day) for day in changed["days"]]
        changed["days"][0]["dcc_hours"] = "7.5"
        updated = client.put(f"{path}/{job_plan_id}", json=changed)
        assert updated.status_code == 200
        assert updated.json()["days"][0]["dcc_hours"] == "7.5"

    # A fresh application proves that the plan survives a real database restart.
    with TestClient(app_for(tmp_path)) as client:
        records = client.get(path)
        assert records.status_code == 200
        assert records.json()[0]["days"][0]["dcc_hours"] == "7.500"

    with sqlite3.connect(tmp_path / "leave-planner.sqlite3") as connection:
        events = connection.execute(
            "SELECT action, details FROM audit_events WHERE entity_type = 'job_plan' ORDER BY id"
        ).fetchall()

    assert [action for action, _details in events] == ["created", "updated"]
    assert json.loads(events[1][1])["before"]["days"][0]["dcc_hours"] == "8.000"


def test_mismatch_needs_reason_and_effective_periods_cannot_overlap(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        consultant_id, leave_year_id = setup_leave_year(client)
        path = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/job-plans"
        mismatch = workbook_job_plan()
        mismatch["spa_pas"] = "2.5"

        # Preview explains a mismatch, while persistence requires the operator's reason.
        preview = client.post(f"{path}/preview", json=mismatch)
        rejected = client.post(path, json=mismatch)
        assert preview.status_code == 200
        assert preview.json()["is_reconciled"] is False
        assert rejected.status_code == 422

        mismatch["reconciliation_override_reason"] = "Approved legacy variance"
        assert client.post(path, json=mismatch).status_code == 201

        overlap = workbook_job_plan()
        overlap["reconciliation_override_reason"] = None
        response = client.post(path, json=overlap)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "job_plan_overlap"
