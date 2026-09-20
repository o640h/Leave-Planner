"""Optimistic consistency and workspace invalidation acceptance tests."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from authentication.service import create_account
from database import create_database_engine, create_session_factory, session_scope
from main import create_app
from migrations import upgrade_database
from settings import Settings
from workspaces.live_router import PointerMessage, _parse_message
from workspaces.live_updates import WorkspaceUpdateHub
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
        with (
            pytest.raises(WebSocketDisconnect) as rejected,
            client.websocket_connect(
                "/api/workspace-updates", headers={"Origin": "https://attacker.invalid"}
            ),
        ):
            pass
        assert rejected.value.code == 1008


def test_workspace_socket_delivers_the_current_pointer_to_a_late_viewer(
    tmp_path: Path,
) -> None:
    with TestClient(live_app(tmp_path)) as client:
        sign_in(client)
        socket_headers = {"Origin": "http://testserver"}
        with client.websocket_connect("/api/workspace-updates", headers=socket_headers) as first:
            first.send_json({"type": "view", "view": "consultants"})
            first.send_json(
                {
                    "type": "pointer",
                    "view": "consultants",
                    "x": 0.2,
                    "y": 0.8,
                }
            )
            with client.websocket_connect(
                "/api/workspace-updates", headers=socket_headers
            ) as second:
                second.send_json({"type": "view", "view": "consultants"})
                message = second.receive_json()

        assert message["type"] == "pointer_updated"
        assert message["label"] == "P"
        assert message["view"] == "consultants"
        assert message["x"] == 0.2
        assert message["y"] == 0.8


class RecordingWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.messages: list[dict[str, object]] = []
        self.closed_with: int | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict[str, object]) -> None:
        self.messages.append(payload)

    async def close(self, code: int) -> None:
        self.closed_with = code


def test_live_pointers_are_private_to_a_workspace_and_compatible_view() -> None:
    async def scenario() -> None:
        hub = WorkspaceUpdateHub(asyncio.get_running_loop())
        first = RecordingWebSocket()
        colleague = RecordingWebSocket()
        other_workspace = RecordingWebSocket()
        first_id = await hub.connect(
            10,
            cast(WebSocket, first),
            user_id=1,
            public_id="first-user",
            display_name="Alex Morgan",
        )
        colleague_id = await hub.connect(
            10,
            cast(WebSocket, colleague),
            user_id=2,
            public_id="second-user",
            display_name="Jordan Patel",
        )
        other_id = await hub.connect(
            20,
            cast(WebSocket, other_workspace),
            user_id=3,
            public_id="third-user",
            display_name="Sam Taylor",
        )
        for workspace_id, connection_id in (
            (10, first_id),
            (10, colleague_id),
            (20, other_id),
        ):
            await hub.set_view(workspace_id, connection_id, "planning:2026-09")

        await hub.move_pointer(
            10,
            first_id,
            view="planning:2026-09",
            x=0.25,
            y=0.75,
        )

        late_joiner = RecordingWebSocket()
        late_joiner_id = await hub.connect(
            10,
            cast(WebSocket, late_joiner),
            user_id=4,
            public_id="late-user",
            display_name="Morgan Lee",
        )
        await hub.set_view(10, late_joiner_id, "planning:2026-09")

        assert first.messages == []
        assert other_workspace.messages == []
        assert colleague.messages == [
            {
                "type": "pointer_updated",
                "connection_id": first_id,
                "label": "A",
                "colour_index": colleague.messages[0]["colour_index"],
                "view": "planning:2026-09",
                "x": 0.25,
                "y": 0.75,
            }
        ]
        assert set(colleague.messages[0]) == {
            "type",
            "connection_id",
            "label",
            "colour_index",
            "view",
            "x",
            "y",
        }
        assert late_joiner.messages == [colleague.messages[0]]

        await hub.disconnect(10, first_id)
        assert colleague.messages[-1] == {
            "type": "pointer_removed",
            "connection_id": first_id,
        }
        assert late_joiner.messages[-1] == colleague.messages[-1]

    asyncio.run(scenario())


def test_live_pointer_schema_accepts_supported_pages_without_record_identifiers() -> None:
    consultants = _parse_message('{"type":"pointer","view":"consultants","x":0.2,"y":0.8}')
    assert isinstance(consultants, PointerMessage)
    assert consultants.view == "consultants"

    assert _parse_message('{"type":"pointer","view":"consultants:42","x":0.2,"y":0.8}') is None
