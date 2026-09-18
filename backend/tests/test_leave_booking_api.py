"""Integration tests for the persisted leave-booking workflow."""

import json
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


def setup_workspace(
    client: TestClient,
    *,
    plan: dict[str, Any] | None = None,
) -> tuple[int, int, str]:
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
    assert (
        client.post(
            f"{root}/job-plans",
            json=plan if plan is not None else job_plan(),
        ).status_code
        == 201
    )
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
            "state": "requested",
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
        assert Decimal(preview.json()["requested"]["bookings"]["dcc_hours"]) == Decimal("20.5")
        assert Decimal(preview.json()["approved"]["bookings"]["total_hours"]) == 0

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
        assert Decimal(cancelled.json()["requested"]["bookings"]["total_hours"]) == 0


def test_capped_deduction_details_survive_save_and_restart(tmp_path: Path) -> None:
    capped_plan = {
        **job_plan(),
        "contracted_pas": "12",
        "dcc_pas": "9",
        "spa_pas": "3",
    }
    booking: dict[str, Any] = {
        "start_date": "2025-10-20",
        "end_date": "2025-10-20",
        "state": "approved",
        "note": None,
        "overrides": [],
    }
    expected_factor = Decimal("10") / Decimal("12")

    with TestClient(app_for(tmp_path)) as client:
        _consultant_id, _leave_year_id, root = setup_workspace(client, plan=capped_plan)

        preview = client.post(f"{root}/bookings/preview", json=booking)
        assert preview.status_code == 200
        preview_day = preview.json()["days"][0]

        assert Decimal(preview_day["contracted_pas"]) == Decimal("12")
        assert Decimal(preview_day["deduction_factor"]) == expected_factor
        assert Decimal(preview_day["standard"]["dcc_hours"]) == Decimal("8")
        assert Decimal(preview_day["standard"]["spa_hours"]) == Decimal("0.5")
        assert Decimal(preview_day["deduction"]["dcc_hours"]) == Decimal("8")
        assert Decimal(preview_day["deduction"]["spa_hours"]) == Decimal("0.5")
        assert Decimal(preview_day["calculated_deduction"]["dcc_hours"]) == (
            Decimal("8") * expected_factor
        )
        assert Decimal(preview_day["calculated_deduction"]["spa_hours"]) == (
            Decimal("0.5") * expected_factor
        )
        assert Decimal(preview.json()["approved"]["bookings"]["total_hours"]) == (
            Decimal("8.5") * expected_factor
        )

        created = client.post(f"{root}/bookings", json=booking)
        assert created.status_code == 201

    # A fresh application instance proves these values came from the saved
    # booking-day snapshot rather than the current job plan.
    with TestClient(app_for(tmp_path)) as client:
        planning = client.get(f"{root}/planning")
        assert planning.status_code == 200

        saved_day = planning.json()["bookings"][0]["days"][0]
        assert Decimal(saved_day["contracted_pas"]) == Decimal("12")
        assert Decimal(saved_day["deduction_factor"]) == expected_factor
        assert Decimal(saved_day["standard"]["dcc_hours"]) == Decimal("8")
        assert Decimal(saved_day["standard"]["spa_hours"]) == Decimal("0.5")
        assert Decimal(saved_day["deduction"]["dcc_hours"]) == Decimal("8")
        assert Decimal(saved_day["deduction"]["spa_hours"]) == Decimal("0.5")
        assert Decimal(saved_day["calculated_deduction"]["dcc_hours"]) == (
            Decimal("8") * expected_factor
        )
        assert Decimal(saved_day["calculated_deduction"]["spa_hours"]) == (
            Decimal("0.5") * expected_factor
        )


def test_job_plan_edit_previews_and_regenerates_booking_deductions(tmp_path: Path) -> None:
    booking: dict[str, object] = {
        "start_date": "2025-10-20",
        "end_date": "2025-10-20",
        "state": "approved",
        "note": None,
        "overrides": [],
    }
    changed_plan = {
        **job_plan(),
        "contracted_pas": "10.5",
        "dcc_pas": "8",
        "spa_pas": "2.5",
    }
    expected_factor = Decimal("10") / Decimal("10.5")

    with TestClient(app_for(tmp_path)) as client:
        _consultant_id, _leave_year_id, root = setup_workspace(client)
        created = client.post(f"{root}/bookings", json=booking)
        assert created.status_code == 201
        job_plan_id = client.get(f"{root}/job-plans").json()[0]["id"]

        impact = client.post(
            f"{root}/job-plans/{job_plan_id}/update-impact",
            json=changed_plan,
        )
        assert impact.status_code == 200
        assert impact.json()["affected_bookings"] == 1
        assert impact.json()["affected_booking_days"] == 1
        assert Decimal(impact.json()["current_total_hours"]) == Decimal("8.5")
        assert Decimal(impact.json()["updated_total_hours"]) == Decimal("8.5") * expected_factor
        assert impact.json()["requires_confirmation"] is True

        rejected = client.put(f"{root}/job-plans/{job_plan_id}", json=changed_plan)
        assert rejected.status_code == 409
        assert rejected.json()["error"]["code"] == "job_plan_booking_impact_confirmation_required"
        unchanged = client.get(f"{root}/planning").json()["bookings"][0]["days"][0]
        assert Decimal(unchanged["deduction_factor"]) == Decimal("1")

        updated = client.put(
            f"{root}/job-plans/{job_plan_id}?regenerate_booking_days=true",
            json=changed_plan,
        )
        assert updated.status_code == 200
        planning = client.get(f"{root}/planning").json()
        regenerated = planning["bookings"][0]["days"][0]
        assert Decimal(regenerated["deduction_factor"]) == expected_factor
        assert Decimal(regenerated["deduction"]["total_hours"]) == Decimal("8.5")
        assert Decimal(regenerated["calculated_deduction"]["total_hours"]) == (
            Decimal("8.5") * expected_factor
        )
        assert Decimal(planning["approved"]["bookings"]["total_hours"]) == (
            Decimal("8.5") * expected_factor
        )

    event = row(
        tmp_path,
        "SELECT details FROM audit_events "
        "WHERE entity_type = 'leave_booking' AND action = 'deductions_regenerated'",
    )

    assert event is not None
    details = json.loads(event[0])
    assert Decimal(details["before"][0]["calculated_dcc_hours"]) == Decimal("8")
    assert Decimal(details["after"][0]["calculated_dcc_hours"]) == Decimal("8") * expected_factor


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
                "state": "requested",
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
            "state": "approved",
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
                "state": "approved",
                "overrides": [],
            },
        )
        booking_id = created.json()["bookings"][0]["id"]

        removed = client.delete(f"{root}/bookings/{booking_id}")

        assert removed.status_code == 200
        assert removed.json()["bookings"] == []
        assert Decimal(removed.json()["approved"]["bookings"]["total_hours"]) == 0

    event = row(
        tmp_path,
        "SELECT action, details FROM audit_events "
        "WHERE consultant_id = :consultant_id AND entity_type = 'leave_booking' "
        "ORDER BY id DESC LIMIT 1",
        {"consultant_id": consultant_id},
    )
    assert event is not None
    assert event[0] == "deleted"
    assert '"state": "approved"' in event[1]


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
            json={**first, "start_date": "2026-04-01", "state": "requested"},
        )
        assert overlap.status_code == 200
        assert any(
            warning["code"] == "leave-records.overlapping-bookings"
            for warning in overlap.json()["warnings"]
        )

    events = rows(
        tmp_path,
        "SELECT action FROM audit_events "
        "WHERE consultant_id = :consultant_id AND entity_type = 'leave_booking'",
        {"consultant_id": consultant_id},
    )
    assert events == [("created",)]
