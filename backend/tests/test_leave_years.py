"""Operator-level API tests for consultant leave-year setup."""

import json
from pathlib import Path

from database_queries import rows
from fastapi import FastAPI
from fastapi.testclient import TestClient

from main import create_app
from settings import Settings


def app_for(data_dir: Path) -> FastAPI:
    """Run the real API and migrations against an isolated SQLite database."""

    return create_app(
        settings=Settings(environment="test", data_dir=data_dir, authentication_required=False),
        frontend_dist=data_dir / "no-frontend-build",
    )


def create_consultant(client: TestClient) -> int:
    response = client.post(
        "/api/consultants",
        json={"name": "Dr Alex Morgan", "post_title": "Consultant in Radiology"},
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def test_create_edit_restart_and_audit_leave_year(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        consultant_id = create_consultant(client)

        created = client.post(
            f"/api/consultants/{consultant_id}/leave-years",
            json={
                "start_date": "2025-08-29",
                "end_date": "2026-08-28",
                "employment_start": None,
                "employment_end": None,
            },
        )
        assert created.status_code == 201
        leave_year_id = created.json()["id"]

        # Add a partial-year employment start without changing the leave-year container.
        updated = client.put(
            f"/api/consultants/{consultant_id}/leave-years/{leave_year_id}",
            json={
                "start_date": "2025-08-29",
                "end_date": "2026-08-28",
                "employment_start": "2026-01-01",
                "employment_end": None,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["employment_start"] == "2026-01-01"

    # Starting a fresh app proves both the record and its history were committed to SQLite.
    with TestClient(app_for(tmp_path)) as client:
        records = client.get(f"/api/consultants/{consultant_id}/leave-years")
        assert records.status_code == 200
        assert records.json() == [
            {
                "id": leave_year_id,
                "consultant_id": consultant_id,
                "start_date": "2025-08-29",
                "end_date": "2026-08-28",
                "employment_start": "2026-01-01",
                "employment_end": None,
            }
        ]

    events = rows(tmp_path, "SELECT action, details FROM audit_events ORDER BY id")

    assert [action for action, _details in events] == ["created", "updated"]
    assert json.loads(events[1][1])["before"]["employment_start"] is None
    assert json.loads(events[1][1])["after"]["employment_start"] == "2026-01-01"


def test_overlapping_leave_years_are_rejected(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        consultant_id = create_consultant(client)
        path = f"/api/consultants/{consultant_id}/leave-years"

        first = client.post(
            path,
            json={"start_date": "2025-08-29", "end_date": "2026-08-28"},
        )
        overlap = client.post(
            path,
            json={"start_date": "2026-01-01", "end_date": "2026-12-31"},
        )

    assert first.status_code == 201
    assert overlap.status_code == 409
    assert overlap.json()["error"]["code"] == "leave_year_overlap"


def test_employment_dates_must_stay_inside_the_leave_year(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        consultant_id = create_consultant(client)
        response = client.post(
            f"/api/consultants/{consultant_id}/leave-years",
            json={
                "start_date": "2025-08-29",
                "end_date": "2026-08-28",
                "employment_start": "2025-01-01",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
