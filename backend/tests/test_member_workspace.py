"""Privacy-boundary tests for the linked Member workspace."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from authentication.service import create_account
from consultants.models import Consultant
from database import create_database_engine, create_session_factory, session_scope
from main import create_app
from migrations import upgrade_database
from settings import Settings
from workspaces.models import MEMBER_ROLE, OWNER_ROLE, Workspace, WorkspaceMembership

PASSWORD = "individual-account-password"


def app_for(tmp_path: Path, *, linked: bool = True) -> FastAPI:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            workspace = session.get(Workspace, 1)
            assert workspace is not None
            workspace.name = "Clinical Services"
            owner = create_account(
                session,
                display_name="Workspace Owner",
                email="owner@example.org",
                password=PASSWORD,
                verified_at=datetime.now(UTC),
            )
            member = create_account(
                session,
                display_name="Linked Member",
                email="member@example.org",
                password=PASSWORD,
                verified_at=datetime.now(UTC),
            )
            consultant = Consultant(
                workspace_id=workspace.id,
                name="Linked Consultant",
                post_title="Consultant in Radiology",
            )
            colleague = Consultant(
                workspace_id=workspace.id,
                name="Team Colleague",
                post_title="Private Colleague Title",
            )
            session.add_all((consultant, colleague))
            session.flush()
            session.add_all(
                (
                    WorkspaceMembership(
                        workspace_id=workspace.id,
                        user_id=owner.id,
                        role=OWNER_ROLE,
                    ),
                    WorkspaceMembership(
                        workspace_id=workspace.id,
                        user_id=member.id,
                        role=MEMBER_ROLE,
                        linked_consultant_id=consultant.id if linked else None,
                    ),
                )
            )
    finally:
        engine.dispose()
    return create_app(settings=settings, frontend_dist=tmp_path / "missing-frontend")


def login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    csrf = client.cookies.get("leave_planner_csrf")
    assert csrf
    return {"X-CSRF-Token": csrf, "Origin": "http://testserver"}


def job_plan(start: str, end: str) -> dict[str, Any]:
    return {
        "effective_from": start,
        "effective_until": end,
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
                "dcc_hours": "8" if weekday < 5 else "0",
                "spa_hours": "0",
                "other_hours": "0",
            }
            for weekday in range(7)
        ],
    }


def configure_team(client: TestClient, headers: dict[str, str]) -> tuple[int, int]:
    consultants = client.get("/api/consultants").json()
    linked_id = next(item["id"] for item in consultants if item["name"] == "Linked Consultant")
    colleague_id = next(item["id"] for item in consultants if item["name"] == "Team Colleague")
    year_ids = []
    for consultant_id in (linked_id, colleague_id):
        year = client.post(
            f"/api/consultants/{consultant_id}/leave-years",
            json={
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "employment_start": "2026-02-01" if consultant_id == linked_id else None,
                "employment_end": None,
            },
            headers=headers,
        ).json()
        year_id = int(year["id"])
        year_ids.append(year_id)
        root = f"/api/consultants/{consultant_id}/leave-years/{year_id}"
        assert (
            client.post(
                f"{root}/job-plans",
                json=job_plan("2026-01-01", "2027-01-01"),
                headers=headers,
            ).status_code
            == 201
        )
        assert (
            client.put(
                f"{root}/entitlement",
                json={"mode": "calculated", "seven_years_or_more": True, "other_hours": "0"},
                headers=headers,
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"{root}/bookings",
                json={
                    "start_date": "2026-09-21",
                    "end_date": "2026-09-22",
                    "state": "approved" if consultant_id == linked_id else "requested",
                    "note": "Own visible note" if consultant_id == linked_id else "Private note",
                    "overrides": [],
                },
                headers=headers,
            ).status_code
            == 201
        )
    return linked_id, year_ids[0]


def test_linked_member_receives_own_read_only_workspace_and_safe_wallchart(
    tmp_path: Path,
) -> None:
    app = app_for(tmp_path)
    with TestClient(app) as owner_client:
        headers = login(owner_client, "owner@example.org")
        linked_id, year_id = configure_team(owner_client, headers)

    with TestClient(app) as member_client:
        login(member_client, "member@example.org")
        response = member_client.get("/api/member/workspace")
        wallchart = member_client.get("/api/member/wallchart?month=2026-09-01")
        operator_response = member_client.get("/api/consultants")
        guessed_response = member_client.get(
            f"/api/consultants/{linked_id}/leave-years/{year_id}/summary"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "linked"
    assert payload["consultant"] == {
        "name": "Linked Consultant",
        "post_title": "Consultant in Radiology",
    }
    assert payload["selected_year"]["leave_year"]["employment_start"] == "2026-02-01"
    assert Decimal(payload["selected_year"]["job_plans"][0]["days"][0]["dcc_hours"]) == Decimal("8")
    assert payload["selected_year"]["entitlement"]["application"]["mode"] == "calculated"
    assert payload["selected_year"]["bookings"][0]["note"] == "Own visible note"
    serialized = response.text
    for private_field in (
        '"consultant_id"',
        '"job_plan_id"',
        '"booking_id"',
        '"audit_events"',
        '"actor_label"',
        '"created_at"',
    ):
        assert private_field not in serialized

    assert wallchart.status_code == 200
    shared = wallchart.json()
    assert shared["people"] == [
        {
            "display_name": "Linked Consultant",
            "leave_dates": [
                {"leave_date": "2026-09-21", "state": "approved"},
                {"leave_date": "2026-09-22", "state": "approved"},
            ],
        },
        {
            "display_name": "Team Colleague",
            "leave_dates": [
                {"leave_date": "2026-09-21", "state": "requested"},
                {"leave_date": "2026-09-22", "state": "requested"},
            ],
        },
    ]
    wallchart_text = wallchart.text
    for private_value in (
        "Private Colleague Title",
        "Private note",
        '"id"',
        '"dcc_hours"',
    ):
        assert private_value not in wallchart_text
    assert operator_response.status_code == 403
    assert guessed_response.status_code == 403


def test_unlinked_member_receives_only_the_waiting_state(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path, linked=False)) as client:
        login(client, "member@example.org")
        workspace = client.get("/api/member/workspace")
        wallchart = client.get("/api/member/wallchart?month=2026-09-01")

    assert workspace.status_code == 200
    assert workspace.json() == {
        "state": "waiting",
        "workspace_name": "Clinical Services",
        "consultant": None,
        "leave_years": [],
        "selected_year": None,
    }
    assert wallchart.status_code == 403
    assert wallchart.json()["error"]["code"] == "member_link_required"


def test_operator_cannot_use_member_only_contract(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        login(client, "owner@example.org")
        response = client.get("/api/member/workspace")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "workspace_role_denied"


def test_member_leave_requests_and_reviewed_approved_cancellation(tmp_path: Path) -> None:
    app = app_for(tmp_path)
    with TestClient(app) as owner_client:
        owner_headers = login(owner_client, "owner@example.org")
        linked_id, year_id = configure_team(owner_client, owner_headers)

    with TestClient(app) as member_client:
        member_headers = login(member_client, "member@example.org")
        request = {
            "start_date": "2026-09-28",
            "end_date": "2026-09-29",
            "note": "Member conference request",
        }
        preview = member_client.post(
            f"/api/member/leave-years/{year_id}/requests/preview",
            json=request,
            headers=member_headers,
        )
        submitted = member_client.post(
            f"/api/member/leave-years/{year_id}/requests",
            json=request,
            headers=member_headers,
        )

    assert preview.status_code == 200
    assert preview.json()["requested"] is not None
    assert submitted.status_code == 201
    submitted_booking = next(
        item
        for item in submitted.json()["selected_year"]["bookings"]
        if item["note"] == "Member conference request"
    )
    assert submitted_booking["state"] == "requested"
    booking_id = int(submitted_booking["id"])

    with TestClient(app) as owner_client:
        owner_headers = login(owner_client, "owner@example.org")
        queue = owner_client.get("/api/leave-requests")
        review = owner_client.get(
            f"/api/consultants/{linked_id}/leave-years/{year_id}/bookings/{booking_id}/review"
        )
        approved = owner_client.post(
            f"/api/consultants/{linked_id}/leave-years/{year_id}/bookings/{booking_id}/approve",
            headers=owner_headers,
        )

    assert queue.status_code == 200
    queued = next(item for item in queue.json()["requests"] if item["booking_id"] == booking_id)
    assert queued["kind"] == "leave_request"
    assert review.status_code == 200
    assert review.json()["kind"] == "leave_request"
    assert review.json()["current_approved"] != review.json()["resulting_approved"]
    assert approved.status_code == 200
    assert next(item for item in approved.json()["bookings"] if item["id"] == booking_id)[
        "state"
    ] == "approved"

    with TestClient(app) as member_client:
        member_headers = login(member_client, "member@example.org")
        cancellation = member_client.post(
            f"/api/member/leave-years/{year_id}/bookings/{booking_id}/request-cancellation",
            headers=member_headers,
        )

    assert cancellation.status_code == 200
    pending = next(
        item
        for item in cancellation.json()["selected_year"]["bookings"]
        if item["id"] == booking_id
    )
    assert pending["state"] == "approved"
    assert pending["cancellation_requested_at"] is not None

    with TestClient(app) as owner_client:
        owner_headers = login(owner_client, "owner@example.org")
        review = owner_client.get(
            f"/api/consultants/{linked_id}/leave-years/{year_id}/bookings/{booking_id}/review"
        )
        cancelled = owner_client.post(
            f"/api/consultants/{linked_id}/leave-years/{year_id}/bookings/{booking_id}/approve-cancellation",
            headers=owner_headers,
        )

    assert review.status_code == 200
    assert review.json()["kind"] == "cancellation_request"
    assert review.json()["current_approved"] != review.json()["resulting_approved"]
    cancelled_booking = next(
        item for item in cancelled.json()["bookings"] if item["id"] == booking_id
    )
    assert cancelled_booking["state"] == "cancelled"
    assert cancelled_booking["cancellation_requested_at"] is None


def test_member_can_cancel_only_a_pending_request(tmp_path: Path) -> None:
    app = app_for(tmp_path)
    with TestClient(app) as owner_client:
        owner_headers = login(owner_client, "owner@example.org")
        _, year_id = configure_team(owner_client, owner_headers)

    with TestClient(app) as member_client:
        member_headers = login(member_client, "member@example.org")
        submitted = member_client.post(
            f"/api/member/leave-years/{year_id}/requests",
            json={
                "start_date": "2026-10-05",
                "end_date": "2026-10-05",
                "note": None,
            },
            headers=member_headers,
        )
        booking = next(
            item
            for item in submitted.json()["selected_year"]["bookings"]
            if item["start_date"] == "2026-10-05"
        )
        cancelled = member_client.post(
            f"/api/member/leave-years/{year_id}/bookings/{booking['id']}/cancel",
            headers=member_headers,
        )

    assert cancelled.status_code == 200
    cancelled_booking = next(
        item
        for item in cancelled.json()["selected_year"]["bookings"]
        if item["id"] == booking["id"]
    )
    assert cancelled_booking["state"] == "cancelled"
