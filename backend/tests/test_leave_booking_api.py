"""Integration tests for the persisted leave-booking workflow."""

import sqlite3
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


def setup_workspace(client: TestClient) -> tuple[int, int, str]:
    consultant = client.post(
        "/api/consultants",
        json={"name": "Workbook Consultant", "post_title": "Consultant"},
    ).json()
    consultant_id = int(consultant["id"])
    year = client.post(
        f"/api/consultants/{consultant_id}/leave-years",
        json={"start_date": "2025-08-29", "end_date": "2026-08-28"},
    ).json()
    leave_year_id = int(year["id"])
    root = f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}"
    assert client.post(f"{root}/job-plans", json=job_plan()).status_code == 201
    assert (
        client.put(
            f"{root}/entitlement",
            json={
                "mode": "manual",
                "dcc_hours": "203.304",
                "spa_hours": "88.064",
                "other_hours": "0",
                "reason": "Workbook reference values",
            },
        ).status_code
        == 200
    )
    return consultant_id, leave_year_id, root


def test_preview_save_reload_and_cancel_booking(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        _consultant_id, _leave_year_id, root = setup_workspace(client)
        booking: dict[str, Any] = {
            "start_date": "2025-10-20",
            "end_date": "2025-10-22",
            "state": "planned",
            "note": None,
            "overrides": [],
        }

        # Monday through Wednesday follows the workbook's visible weekday pattern.
        preview = client.post(f"{root}/bookings/preview", json=booking)
        assert preview.status_code == 200
        assert [Decimal(day["deduction"]["total_hours"]) for day in preview.json()["days"]] == [
            Decimal("8.5"),
            Decimal("10"),
            Decimal("6"),
        ]
        assert Decimal(preview.json()["projected"]["bookings"]["dcc_hours"]) == Decimal("20.5")
        assert Decimal(preview.json()["confirmed"]["bookings"]["total_hours"]) == 0

        created = client.post(f"{root}/bookings", json=booking)
        assert created.status_code == 201
        booking_id = created.json()["bookings"][0]["id"]

    # A new application instance proves both the booking and daily snapshots survive restart.
    with TestClient(app_for(tmp_path)) as client:
        planning = client.get(f"{root}/planning")
        assert planning.status_code == 200
        assert Decimal(
            planning.json()["bookings"][0]["days"][2]["deduction"]["spa_hours"]
        ) == Decimal("1.5")

        cancelled = client.post(f"{root}/bookings/{booking_id}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["bookings"][0]["state"] == "cancelled"
        assert Decimal(cancelled.json()["projected"]["bookings"]["total_hours"]) == 0


def test_daily_override_and_public_holiday_are_not_double_deducted(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        _consultant_id, _leave_year_id, root = setup_workspace(client)
        override = client.post(
            f"{root}/bookings/preview",
            json={
                "start_date": "2025-10-22",
                "end_date": "2025-10-22",
                "state": "approved",
                "overrides": [
                    {
                        "leave_date": "2025-10-22",
                        "dcc_hours": "4.5",
                        "spa_hours": "0",
                        "reason": "SPA activity retained",
                    }
                ],
            },
        )
        assert override.status_code == 200
        assert Decimal(override.json()["days"][0]["deduction"]["total_hours"]) == Decimal("4.5")
        assert override.json()["days"][0]["override_reason"] == "SPA activity retained"

        christmas = client.post(
            f"{root}/bookings/preview",
            json={
                "start_date": "2025-12-25",
                "end_date": "2025-12-25",
                "state": "planned",
                "overrides": [],
            },
        )
        assert christmas.status_code == 200
        day = christmas.json()["days"][0]
        assert day["public_holiday_name"] == "Christmas Day"
        assert Decimal(day["deduction"]["total_hours"]) == 0


def test_existing_booking_can_be_updated_with_an_optional_override_reason(
    tmp_path: Path,
) -> None:
    with TestClient(app_for(tmp_path)) as client:
        _consultant_id, _leave_year_id, root = setup_workspace(client)
        booking = {
            "start_date": "2025-12-31",
            "end_date": "2025-12-31",
            "state": "taken",
            "overrides": [],
        }
        created = client.post(f"{root}/bookings", json=booking)
        booking_id = created.json()["bookings"][0]["id"]

        # Editing replaces the stored daily snapshot without colliding with its date key.
        updated = client.put(
            f"{root}/bookings/{booking_id}",
            json={
                **booking,
                "overrides": [
                    {
                        "leave_date": "2025-12-31",
                        "dcc_hours": "4",
                        "spa_hours": "0",
                    }
                ],
            },
        )

        assert updated.status_code == 200
        saved_day = updated.json()["bookings"][0]["days"][0]
        assert Decimal(saved_day["deduction"]["dcc_hours"]) == Decimal("4")
        assert Decimal(saved_day["deduction"]["spa_hours"]) == 0
        assert saved_day["override_reason"] is None


def test_incorrect_booking_can_be_removed_without_losing_audit_evidence(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        consultant_id, _leave_year_id, root = setup_workspace(client)
        created = client.post(
            f"{root}/bookings",
            json={
                "start_date": "2025-12-31",
                "end_date": "2025-12-31",
                "state": "taken",
                "overrides": [],
            },
        )
        booking_id = created.json()["bookings"][0]["id"]

        removed = client.delete(f"{root}/bookings/{booking_id}")

        assert removed.status_code == 200
        assert removed.json()["bookings"] == []
        assert Decimal(removed.json()["actual"]["bookings"]["total_hours"]) == 0

    with sqlite3.connect(tmp_path / "leave-planner.sqlite3") as connection:
        event = connection.execute(
            "SELECT action, details FROM audit_events "
            "WHERE consultant_id = ? AND entity_type = 'leave_booking' "
            "ORDER BY id DESC LIMIT 1",
            (consultant_id,),
        ).fetchone()
    assert event is not None
    assert event[0] == "deleted"
    assert '"state": "taken"' in event[1]


def test_overlap_warning_and_audit_history(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        consultant_id, _leave_year_id, root = setup_workspace(client)
        first = {
            "start_date": "2026-03-30",
            "end_date": "2026-04-01",
            "state": "approved",
            "overrides": [],
        }
        assert client.post(f"{root}/bookings", json=first).status_code == 201
        overlap = client.post(
            f"{root}/bookings/preview",
            json={**first, "start_date": "2026-04-01", "state": "planned"},
        )
        assert overlap.status_code == 200
        assert any(
            warning["code"] == "leave-records.overlapping-bookings"
            for warning in overlap.json()["warnings"]
        )

    with sqlite3.connect(tmp_path / "leave-planner.sqlite3") as connection:
        events = connection.execute(
            "SELECT action FROM audit_events "
            "WHERE consultant_id = ? AND entity_type = 'leave_booking'",
            (consultant_id,),
        ).fetchall()
    assert events == [("created",)]
