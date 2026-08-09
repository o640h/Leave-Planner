"""Safe-removal API workflows and retained-history checks."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from main import create_app
from settings import Settings


def app_for(data_dir: Path) -> FastAPI:
    return create_app(
        settings=Settings(environment="test", data_dir=data_dir),
        frontend_dist=data_dir / "no-frontend-build",
    )


def job_plan() -> dict[str, Any]:
    visible = {0: ("8", "0.5"), 1: ("8", "2"), 2: ("4.5", "1.5")}
    return {
        "effective_from": "2025-08-29",
        "effective_until": "2026-08-29",
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


def configured_year(client: TestClient) -> tuple[int, int, int]:
    consultant = client.post(
        "/api/consultants",
        json={"name": "Removal Example", "post_title": "Consultant"},
    ).json()
    consultant_id = int(consultant["id"])
    year_path = f"/api/consultants/{consultant_id}/leave-years"
    leave_year = client.post(
        year_path,
        json={"start_date": "2025-08-29", "end_date": "2026-08-28"},
    ).json()
    leave_year_id = int(leave_year["id"])
    plans_path = f"{year_path}/{leave_year_id}/job-plans"
    stored_plan = client.post(plans_path, json=job_plan()).json()
    return consultant_id, leave_year_id, int(stored_plan["id"])


def test_consultant_archive_hides_directory_record_but_retains_history(tmp_path: Path) -> None:
    """Archiving should never cascade-delete a consultant's configured years."""

    with TestClient(app_for(tmp_path)) as client:
        consultant_id, leave_year_id, _ = configured_year(client)
        impact = client.get(f"/api/consultants/{consultant_id}/archive-impact")
        assert impact.status_code == 200
        assert impact.json()["confirmation_text"] == "Removal Example"

        mismatch = client.post(
            f"/api/consultants/{consultant_id}/archive",
            json={"confirmation": "wrong"},
        )
        assert mismatch.status_code == 422

        archived = client.post(
            f"/api/consultants/{consultant_id}/archive",
            json={"confirmation": "Removal Example"},
        )
        assert archived.status_code == 200
        assert client.get("/api/consultants").json() == []
        assert client.get(f"/api/consultants/{consultant_id}").json()["archived_at"] is not None
        assert (
            client.get(f"/api/consultants/{consultant_id}/leave-years").json()[0]["id"]
            == leave_year_id
        )


def test_leave_year_removal_reports_and_deletes_owned_setup_data(tmp_path: Path) -> None:
    """A confirmed setup deletion should cascade while leaving its audit evidence."""

    with TestClient(app_for(tmp_path)) as client:
        consultant_id, leave_year_id, _ = configured_year(client)
        entitlement_path = (
            f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/entitlement"
        )
        client.put(
            entitlement_path,
            json={
                "mode": "manual",
                "dcc_hours": "200",
                "spa_hours": "80",
                "reason": "Approved test value",
            },
        )

        path = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}"
        impact = client.get(f"{path}/removal-impact").json()
        assert "1 job plan(s) will be deleted." in impact["consequences"]
        assert "1 applied entitlement record(s) will be deleted." in impact["consequences"]

        removed = client.post(f"{path}/remove", json={"confirmation": "DELETE"})
        assert removed.status_code == 200
        assert client.get(f"/api/consultants/{consultant_id}/leave-years").json() == []

    with sqlite3.connect(tmp_path / "leave-planner.sqlite3") as connection:
        event = connection.execute(
            "SELECT details FROM audit_events WHERE entity_type = 'leave_year' "
            "AND action = 'deleted' ORDER BY id DESC"
        ).fetchone()
        assert connection.execute("SELECT COUNT(*) FROM job_plan_versions").fetchone() == (0,)

    assert event is not None
    assert json.loads(event[0])["before"]["start_date"] == "2025-08-29"


def test_job_plan_removal_preserves_entitlement_when_it_creates_a_gap(tmp_path: Path) -> None:
    """Deleting required coverage must keep the old applied value visible for review."""

    with TestClient(app_for(tmp_path)) as client:
        consultant_id, leave_year_id, job_plan_id = configured_year(client)
        entitlement_path = (
            f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/entitlement"
        )
        dates = {
            "consultant_appointment_date": "2010-01-01",
            "consultant_service_start_date": "2010-01-01",
        }
        original = client.put(entitlement_path, json={"mode": "calculated", **dates}).json()

        plan_path = (
            f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}"
            f"/job-plans/{job_plan_id}"
        )
        impact = client.get(f"{plan_path}/removal-impact").json()
        assert any("will not cover" in item for item in impact["consequences"])

        removed = client.post(f"{plan_path}/remove", json={"confirmation": "DELETE"})
        assert removed.status_code == 200
        assert removed.json()["entitlement_status"] == "needs_attention"
        assert client.get(entitlement_path).json()["application"] == original["application"]

