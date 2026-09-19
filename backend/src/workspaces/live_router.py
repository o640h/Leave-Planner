"""Authenticated workspace invalidation WebSocket."""

from typing import cast

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session, sessionmaker

from authentication.service import authenticated_user
from database import session_scope
from settings import Settings

from .live_updates import WorkspaceUpdateHub
from .service import membership_for_user

router = APIRouter(tags=["workspace updates"])


@router.websocket("/api/workspace-updates")
async def workspace_updates(websocket: WebSocket) -> None:
    settings = cast(Settings, websocket.app.state.settings)
    origin = websocket.headers.get("origin")
    browser_scheme = "https" if websocket.url.scheme == "wss" else "http"
    expected_origin = settings.public_origin or f"{browser_scheme}://{websocket.url.netloc}"
    if origin is not None and origin.rstrip("/") != expected_origin:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    factory = cast(sessionmaker[Session], websocket.app.state.session_factory)
    with session_scope(factory) as session:
        authenticated = authenticated_user(
            session, websocket.cookies.get(settings.session_cookie_name)
        )
        if authenticated is None:
            await websocket.close(code=4401)
            return
        workspace_id = authenticated.active_workspace_id
        if workspace_id is None or membership_for_user(
            session, authenticated.id, workspace_id
        ) is None:
            await websocket.close(code=4403)
            return

    hub = cast(WorkspaceUpdateHub, websocket.app.state.workspace_update_hub)
    await hub.connect(workspace_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(workspace_id, websocket)
