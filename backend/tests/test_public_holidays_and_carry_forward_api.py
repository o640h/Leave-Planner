"""Integration tests for public-holiday and carry-forward workflows."""

from decimal import Decimal
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


def setup_year(client: TestClient) -> tuple[int, int]:
    consultant = client.post(
        "/api/consultants",
        json={"name": "Dr Alex Morgan", "post_title": "Consultant"},
    ).json()
    leave_year = client.post(
        f"/api/consultants/{consultant['id']}/leave-years",
        json={"start_date": "2025-08-29", "end_date": "2026-08-28"},
    ).json()
    return int(consultant["id"]), int(leave_year["id"])


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


def test_calendar_corrections_and_consultant_treatments_persist(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        consultant_id, leave_year_id = setup_year(client)
        plans = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/job-plans"
        assert client.post(plans, json=job_plan()).status_code == 201

        settings = client.get("/api/settings/public-holidays")
        assert settings.status_code == 200
        assert settings.json()["source"] == "static_snapshot"

        corrected = client.post(
            "/api/settings/public-holidays/corrections",
            json={
                "holiday_date": "2026-08-03",
                "action": "add_or_replace",
                "replacement_name": "Trust Holiday",
                "reason": "Approved local closure",
            },
        )
        assert corrected.status_code == 200
        correction_id = corrected.json()["corrections"][0]["id"]

        year_path = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/public-holidays"
        holidays = client.get(year_path)
        assert any(item["name"] == "Trust Holiday" for item in holidays.json()["occurrences"])

        treated = client.put(
            f"{year_path}/2025-12-25/treatment",
            json={
                "basis": "qualifying_on_call",
                "note": "Operator confirmed qualifying on-call cover",
                "worked_date": None,
            },
        )
        christmas = next(
            item for item in treated.json()["occurrences"] if item["holiday_date"] == "2025-12-25"
        )
        assert christmas["basis"] == "qualifying_on_call"
        assert christmas["dcc_deduction_hours"] == "0"

        assert (
            client.delete(f"/api/settings/public-holidays/corrections/{correction_id}").status_code
            == 200
        )


def test_carry_forward_can_be_set_and_cleared(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        consultant_id, leave_year_id = setup_year(client)
        path = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/carry-forward"

        carry = client.put(path, json={"hours": "41.25"})
        assert carry.status_code == 200
        assert Decimal(carry.json()["hours"]) == Decimal("41.25")
        assert Decimal(client.get(path).json()["hours"]) == Decimal("41.25")

        cleared = client.put(path, json={"hours": "0"})
        assert cleared.status_code == 200
        assert Decimal(cleared.json()["hours"]) == Decimal("0")

        rejected = client.put(path, json={"hours": "-1"})
        assert rejected.status_code == 422


def test_entitlement_exposes_workbook_policy_components(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        consultant_id, leave_year_id = setup_year(client)
        plans = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/job-plans"
        client.post(plans, json=job_plan())
        preview = client.post(
            f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/entitlement/preview",
            params={
                "consultant_appointment_date": "2012-01-18",
                "consultant_service_start_date": "2012-01-18",
            },
        )
        assert preview.status_code == 200
        labels = {item["label"] for item in preview.json()["components"]}
        assert labels == {
            "Basic Leave",
            "Statutory Days",
            "Seniority",
            "Hospital R&R",
        }
        assert Decimal(preview.json()["recommended_entitlement"]["total_hours"]) == Decimal(
            "291.368"
        )
