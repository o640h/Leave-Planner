"""Operator-level API tests for entitlement recommendation and application."""

import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from main import create_app
from settings import Settings


def app_for(data_dir: Path) -> FastAPI:
    """Run the real API and migrations against an isolated database."""

    return create_app(
        settings=Settings(environment="test", data_dir=data_dir),
        frontend_dist=data_dir / "no-frontend-build",
    )


def complete_job_plan() -> dict[str, Any]:
    """Return the workbook PA split covering the complete leave year."""

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
        "reconciliation_override_reason": None,
        "days": days,
    }


def setup_year(client: TestClient) -> tuple[int, int]:
    consultant = client.post(
        "/api/consultants",
        json={"name": "Workbook Example", "post_title": "Consultant"},
    ).json()
    consultant_id = int(consultant["id"])

    leave_year = client.post(
        f"/api/consultants/{consultant_id}/leave-years",
        json={"start_date": "2025-08-29", "end_date": "2026-08-28"},
    ).json()
    leave_year_id = int(leave_year["id"])

    response = client.post(
        f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/job-plans",
        json=complete_job_plan(),
    )
    assert response.status_code == 201
    return consultant_id, leave_year_id


def test_calculated_entitlement_matches_the_workbook_and_survives_restart(
    tmp_path: Path,
) -> None:
    """The API should expose and persist the workbook recommendation."""

    with TestClient(app_for(tmp_path)) as client:
        consultant_id, leave_year_id = setup_year(client)
        path = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/entitlement"
        dates = {
            "consultant_appointment_date": "2010-01-01",
            "consultant_service_start_date": "2010-01-01",
        }

        # Preview is read-only and explains base plus public-holiday hours.
        preview = client.post(f"{path}/preview", params=dates)
        assert preview.status_code == 200
        recommendation = preview.json()
        assert Decimal(recommendation["base_entitlement"]["total_hours"]) == Decimal("243.936")
        assert Decimal(recommendation["public_holiday_entitlement"]["total_hours"]) == Decimal(
            "47.432"
        )
        assert Decimal(recommendation["recommended_entitlement"]["total_hours"]) == Decimal(
            "291.368"
        )

        # Calculated mode applies the recommendation without editable totals.
        applied = client.put(path, json={"mode": "calculated", **dates})
        assert applied.status_code == 200
        body = applied.json()
        assert Decimal(body["application"]["entitlement"]["dcc_hours"]) == Decimal("203.304")
        assert Decimal(body["application"]["entitlement"]["spa_hours"]) == Decimal("88.064")
        assert body["recommendation"]["trace"]

    # A fresh app instance proves both the application and linked snapshot persist.
    with TestClient(app_for(tmp_path)) as client:
        stored = client.get(path)
        assert stored.status_code == 200
        assert stored.json()["application"]["mode"] == "calculated"
        assert stored.json()["recommendation"] is not None


def test_manual_entitlement_requires_a_reason_and_replaces_the_applied_values(
    tmp_path: Path,
) -> None:
    """Manual control should remain explicit, traceable, and independent of dates."""

    with TestClient(app_for(tmp_path)) as client:
        consultant_id, leave_year_id = setup_year(client)
        path = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/entitlement"
        without_reason = {
            "mode": "manual",
            "dcc_hours": "210",
            "spa_hours": "90",
            "other_hours": "0",
        }
        assert client.put(path, json=without_reason).status_code == 422

        applied = client.put(
            path,
            json={**without_reason, "reason": "Trust-approved starting values"},
        )
        assert applied.status_code == 200
        assert applied.json()["recommendation"] is None
        assert Decimal(applied.json()["application"]["entitlement"]["total_hours"]) == Decimal(
            "300"
        )

    with sqlite3.connect(tmp_path / "leave-planner.sqlite3") as connection:
        event = connection.execute(
            "SELECT details FROM audit_events "
            "WHERE entity_type = 'applied_entitlement' ORDER BY id DESC"
        ).fetchone()

    assert event is not None
    assert json.loads(event[0])["after"]["reason"] == "Trust-approved starting values"


def test_calculation_is_blocked_when_job_plan_dates_have_a_gap(
    tmp_path: Path,
) -> None:
    """A missing plan must not silently produce a partial entitlement."""

    with TestClient(app_for(tmp_path)) as client:
        consultant_id, leave_year_id = setup_year(client)
        job_plans_path = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/job-plans"
        stored_plan = client.get(job_plans_path).json()[0]
        stored_plan["effective_until"] = "2026-08-01"
        assert (
            client.put(
                f"{job_plans_path}/{stored_plan['id']}",
                json=stored_plan,
            ).status_code
            == 200
        )

        response = client.post(
            f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/entitlement/preview",
            params={
                "consultant_appointment_date": "2010-01-01",
                "consultant_service_start_date": "2010-01-01",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "job_plan_gap"


def test_refresh_recalculates_a_calculated_entitlement_after_job_plan_change(
    tmp_path: Path,
) -> None:
    """Changing a source fact should update calculated applied values automatically."""

    with TestClient(app_for(tmp_path)) as client:
        consultant_id, leave_year_id = setup_year(client)
        entitlement_path = (
            f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/entitlement"
        )
        dates = {
            "consultant_appointment_date": "2010-01-01",
            "consultant_service_start_date": "2010-01-01",
        }
        original = client.put(entitlement_path, json={"mode": "calculated", **dates}).json()

        job_plans_path = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/job-plans"
        job_plan = client.get(job_plans_path).json()[0]
        job_plan["dcc_pas"] = "4.235"
        job_plan["spa_pas"] = "4.235"
        assert client.put(f"{job_plans_path}/{job_plan['id']}", json=job_plan).status_code == 200

        refreshed = client.post(f"{entitlement_path}/refresh")

    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["recommendation"]["id"] != original["recommendation"]["id"]
    assert Decimal(body["application"]["entitlement"]["dcc_hours"]) == Decimal("145.684")
    assert Decimal(body["application"]["entitlement"]["spa_hours"]) == Decimal("145.684")


def test_refresh_preserves_a_manual_entitlement(tmp_path: Path) -> None:
    """Automatic refresh must never replace values the operator entered manually."""

    with TestClient(app_for(tmp_path)) as client:
        consultant_id, leave_year_id = setup_year(client)
        path = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}/entitlement"
        applied = client.put(
            path,
            json={
                "mode": "manual",
                "dcc_hours": "210",
                "spa_hours": "90",
                "reason": "Trust-approved starting values",
            },
        ).json()

        refreshed = client.post(f"{path}/refresh")

    assert refreshed.status_code == 200
    assert refreshed.json() == applied
