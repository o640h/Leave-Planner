"""Optimistic consistency and workspace invalidation acceptance tests."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from authentication.service import create_account
from database import create_database_engine, create_session_factory, session_scope
from main import create_app
from migrations import upgrade_database
from settings import Settings
from workspaces.models import OWNER_ROLE, Workspace, WorkspaceMembership

EMAIL = "owner@example.org"
PASSWORD = "workspace-password"


def live_app(tmp_path: Path) -> FastAPI:
    settings = Settings(environment="development", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            owner = create_account(
                session,
                display_name="Primary Owner",
                email=EMAIL,
                password=PASSWORD,
                verified_at=datetime.now(UTC),
            )
            workspace = Workspace(name="Consultant Team")
            session.add(workspace)
            session.flush()
            session.add(
                WorkspaceMembership(
                    workspace_id=workspace.id,
                    user_id=owner.id,
                    role=OWNER_ROLE,
                )
            )
            owner.last_workspace_id = workspace.id
    finally:
        engine.dispose()
    return create_app(settings=settings, frontend_dist=tmp_path / "missing-frontend")


def sign_in(client: TestClient) -> tuple[dict[str, str], int]:
    response = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200
    csrf = client.cookies.get("leave_planner_csrf")
    revision = response.json()["workspace"]["revision"]
    assert csrf
    assert isinstance(revision, int)
    return {"Origin": "http://testserver", "X-CSRF-Token": csrf}, revision


def test_committed_write_publishes_invalidation_and_rejects_stale_edit(
    tmp_path: Path,
) -> None:
    with TestClient(live_app(tmp_path)) as client:
        headers, revision = sign_in(client)

        missing_revision = client.post(
            "/api/consultants",
            json={"name": "Missing Revision", "post_title": None},
            headers=headers,
        )
        assert missing_revision.status_code == 428
        assert missing_revision.json()["error"]["code"] == "workspace_revision_required"

        with client.websocket_connect(
            "/api/workspace-updates", headers={"Origin": "http://testserver"}
        ) as websocket:
            current_headers = {**headers, "If-Match": str(revision)}
            created = client.post(
                "/api/consultants",
                json={"name": "Dr Alex Morgan", "post_title": "Radiology"},
                headers=current_headers,
            )
            assert created.status_code == 201
            assert created.headers["X-Workspace-Revision"] == str(revision + 1)
            assert websocket.receive_json() == {
                "type": "workspace_invalidated",
                "revision": revision + 1,
                "scopes": ["consultants", "member-workspace", "planning"],
            }

            stale = client.post(
                "/api/consultants",
                json={"name": "Stale Edit", "post_title": None},
                headers=current_headers,
            )
            assert stale.status_code == 409
            assert stale.json()["error"]["code"] == "stale_workspace_data"

        refreshed = client.get("/api/consultants")
        assert refreshed.status_code == 200
        assert refreshed.headers["X-Workspace-Revision"] == str(revision + 1)
        assert [consultant["name"] for consultant in refreshed.json()] == ["Dr Alex Morgan"]

        retried = client.post(
            "/api/consultants",
            json={"name": "Dr Jordan Patel", "post_title": None},
            headers={**headers, "If-Match": refreshed.headers["X-Workspace-Revision"]},
        )
        assert retried.status_code == 201
        assert retried.headers["X-Workspace-Revision"] == str(revision + 2)


def test_workspace_socket_rejects_an_untrusted_origin(tmp_path: Path) -> None:
    with TestClient(live_app(tmp_path)) as client:
        sign_in(client)
        with pytest.raises(WebSocketDisconnect) as rejected, client.websocket_connect(
            "/api/workspace-updates", headers={"Origin": "https://attacker.invalid"}
        ):
            pass
        assert rejected.value.code == 1008
