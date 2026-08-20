"""Integration tests for public-holiday and carry-forward workflows."""

from decimal import Decimal
from pathlib import Path
from typing import Any

from database_queries import row, rows
from fastapi import FastAPI
from fastapi.testclient import TestClient

from main import create_app
from settings import Settings


def app_for(data_dir: Path) -> FastAPI:
    return create_app(
        settings=Settings(environment="test", data_dir=data_dir, authentication_required=False),
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

        treatment_path = f"{year_path}/2026-04-06/treatment"
        treated = client.put(
            treatment_path,
            json={
                "basis": "qualifying_on_call",
            },
        )
        easter_monday = next(
            item for item in treated.json()["occurrences"] if item["holiday_date"] == "2026-04-06"
        )
        assert easter_monday["basis"] == "qualifying_on_call"
        assert easter_monday["treatment_note"] is None
        assert easter_monday["dcc_deduction_hours"] == "0"

        restored = client.put(
            treatment_path,
            json={"basis": "standard", "note": None},
        )
        easter_monday = next(
            item for item in restored.json()["occurrences"] if item["holiday_date"] == "2026-04-06"
        )
        assert easter_monday["basis"] == "standard"
        assert easter_monday["dcc_deduction_hours"] == "8.000"
        assert easter_monday["spa_deduction_hours"] == "0.500"

        assert (
            client.delete(f"/api/settings/public-holidays/corrections/{correction_id}").status_code
            == 200
        )

    assert row(tmp_path, "SELECT COUNT(*) FROM public_holiday_treatments") == (0,)
    actions = rows(
        tmp_path,
        "SELECT action FROM audit_events WHERE entity_type = 'public_holiday_treatment' "
        "ORDER BY id",
    )
    assert actions == [("created",), ("deleted",)]


def test_carry_forward_can_be_set_and_cleared(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        consultant_id, leave_year_id = setup_year(client)
        path = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/carry-forward"

        carry = client.put(path, json={"dcc_hours": "41.25", "spa_hours": "3.5"})
        assert carry.status_code == 200
        assert Decimal(carry.json()["dcc_hours"]) == Decimal("41.25")
        assert Decimal(carry.json()["spa_hours"]) == Decimal("3.5")
        assert Decimal(carry.json()["total_hours"]) == Decimal("44.75")
        assert Decimal(client.get(path).json()["spa_hours"]) == Decimal("3.5")

        cleared = client.put(path, json={"dcc_hours": "0", "spa_hours": "0"})
        assert cleared.status_code == 200
        assert Decimal(cleared.json()["total_hours"]) == Decimal("0")

        rejected = client.put(path, json={"dcc_hours": "-1", "spa_hours": "0"})
        assert rejected.status_code == 422


def test_dcc_and_spa_carry_forward_reach_each_balance_component(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        consultant_id, leave_year_id = setup_year(client)
        root = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}"
        assert client.post(f"{root}/job-plans", json=job_plan()).status_code == 201
        assert client.put(
            f"{root}/entitlement",
            json={"mode": "calculated", "seven_years_or_more": True, "other_hours": "0"},
        ).status_code == 200
        assert client.put(
            f"{root}/carry-forward",
            json={"dcc_hours": "5.25", "spa_hours": "2.5"},
        ).status_code == 200

        planning = client.get(f"{root}/planning")

    assert planning.status_code == 200
    projected = planning.json()["projected"]
    assert Decimal(projected["carry_forward"]["dcc_hours"]) == Decimal("5.25")
    assert Decimal(projected["carry_forward"]["spa_hours"]) == Decimal("2.5")


def test_entitlement_exposes_workbook_policy_components(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        consultant_id, leave_year_id = setup_year(client)
        plans = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/job-plans"
        client.post(plans, json=job_plan())
        preview = client.post(
            f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/entitlement/preview",
            params={"seven_years_or_more": True},
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
