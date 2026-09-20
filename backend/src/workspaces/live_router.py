"""Authenticated workspace invalidation and ephemeral pointer WebSocket."""

import asyncio
import json
from typing import Literal, cast

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session, sessionmaker

from authentication.service import authenticated_user
from database import session_scope
from settings import Settings

from .live_updates import WorkspaceUpdateHub
from .service import membership_for_user

router = APIRouter(tags=["workspace updates"])

MAX_MESSAGE_BYTES = 512
HEARTBEAT_TIMEOUT_SECONDS = 180
VIEW_PATTERN = r"^(?:consultants|planning:\d{4}-(0[1-9]|1[0-2]))$"


class ViewMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["view"]
    view: str | None = Field(default=None, pattern=VIEW_PATTERN)


class PointerMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["pointer"]
    view: str = Field(pattern=VIEW_PATTERN)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class PointerHiddenMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["pointer_hidden"]


class HeartbeatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["heartbeat"]


type LiveMessage = ViewMessage | PointerMessage | PointerHiddenMessage | HeartbeatMessage

MESSAGE_MODELS: dict[str, type[BaseModel]] = {
    "view": ViewMessage,
    "pointer": PointerMessage,
    "pointer_hidden": PointerHiddenMessage,
    "heartbeat": HeartbeatMessage,
}


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
        if (
            workspace_id is None
            or membership_for_user(session, authenticated.id, workspace_id) is None
        ):
            await websocket.close(code=4403)
            return

    hub = cast(WorkspaceUpdateHub, websocket.app.state.workspace_update_hub)
    connection_id = await hub.connect(
        workspace_id,
        websocket,
        user_id=authenticated.id,
        public_id=authenticated.public_id,
        display_name=authenticated.display_name,
    )
    try:
        while True:
            raw_message = await asyncio.wait_for(
                websocket.receive_text(), timeout=HEARTBEAT_TIMEOUT_SECONDS
            )
            message = _parse_message(raw_message)
            if message is None:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            if isinstance(message, ViewMessage):
                await hub.set_view(workspace_id, connection_id, message.view)
            elif isinstance(message, PointerMessage):
                await hub.move_pointer(
                    workspace_id,
                    connection_id,
                    view=message.view,
                    x=message.x,
                    y=message.y,
                )
            elif isinstance(message, PointerHiddenMessage):
                await hub.hide_pointer(workspace_id, connection_id)
    except TimeoutError:
        await websocket.close(code=4408)
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(workspace_id, connection_id)


def _parse_message(raw_message: str) -> LiveMessage | None:
    if len(raw_message.encode("utf-8")) > MAX_MESSAGE_BYTES:
        return None
    try:
        payload = json.loads(raw_message)
        if not isinstance(payload, dict):
            return None
        message_type = payload.get("type")
        if not isinstance(message_type, str):
            return None
        model = MESSAGE_MODELS.get(message_type)
        return cast(LiveMessage, model.model_validate(payload)) if model is not None else None
    except json.JSONDecodeError, ValidationError:
        return None
