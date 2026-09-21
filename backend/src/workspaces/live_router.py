"""Authenticated workspace invalidation and ephemeral pointer WebSocket."""

import asyncio
import json
import logging
from collections import deque
from time import monotonic
from typing import Literal, cast

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session, sessionmaker

from authentication.service import AuthenticatedUser, authenticated_user
from database import session_scope
from http_security import SecurityRateLimits, client_key
from settings import Settings

from .live_updates import WorkspaceConnectionLimit, WorkspaceUpdateHub
from .service import membership_for_user

router = APIRouter(tags=["workspace updates"])
logger = logging.getLogger(__name__)

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
    if origin is None or origin.rstrip("/") != expected_origin:
        logger.warning("workspace_websocket_rejected", extra={"reason": "origin"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    peer = websocket.client.host if websocket.client is not None else None
    address = client_key(
        peer_host=peer,
        cloudflare_connecting_ip=websocket.headers.get("cf-connecting-ip"),
        settings=settings,
    )
    if address is None:
        logger.warning("workspace_websocket_rejected", extra={"reason": "client_address"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    limits = cast(SecurityRateLimits, websocket.app.state.security_rate_limits)
    if limits.websocket_connections.retry_after(
        address, limit=settings.websocket_connection_rate_limit
    ):
        logger.warning("workspace_websocket_rate_limited", extra={"reason": "connections"})
        await websocket.close(code=4429)
        return

    factory = cast(sessionmaker[Session], websocket.app.state.session_factory)
    authenticated = _validate_access(
        factory,
        websocket.cookies.get(settings.session_cookie_name),
    )
    if authenticated is None:
        logger.warning("workspace_websocket_rejected", extra={"reason": "authentication"})
        await websocket.close(code=4401)
        return
    workspace_id = authenticated.active_workspace_id
    if workspace_id is None:
        logger.warning("workspace_websocket_rejected", extra={"reason": "workspace"})
        await websocket.close(code=4403)
        return

    hub = cast(WorkspaceUpdateHub, websocket.app.state.workspace_update_hub)
    try:
        connection_id = await hub.connect(
            workspace_id,
            websocket,
            user_id=authenticated.id,
            session_id=authenticated.session_id,
            public_id=authenticated.public_id,
            display_name=authenticated.display_name,
            max_connections_for_user=settings.websocket_connections_per_account,
        )
    except WorkspaceConnectionLimit:
        logger.warning("workspace_websocket_rate_limited", extra={"reason": "account_cap"})
        return
    message_times: deque[float] = deque()
    last_message = monotonic()
    last_validation = last_message
    try:
        while True:
            now = monotonic()
            timeout = min(
                HEARTBEAT_TIMEOUT_SECONDS - (now - last_message),
                settings.websocket_revalidation_seconds - (now - last_validation),
            )
            try:
                raw_message = await asyncio.wait_for(
                    websocket.receive_text(), timeout=max(0.05, timeout)
                )
            except TimeoutError:
                now = monotonic()
                if now - last_message >= HEARTBEAT_TIMEOUT_SECONDS:
                    await websocket.close(code=4408)
                    return
                if not _same_access(
                    factory,
                    websocket.cookies.get(settings.session_cookie_name),
                    authenticated,
                    workspace_id,
                ):
                    logger.warning(
                        "workspace_websocket_closed", extra={"reason": "access_revoked"}
                    )
                    await websocket.close(code=4401)
                    return
                last_validation = now
                continue

            now = monotonic()
            last_message = now
            cutoff = now - 1
            while message_times and message_times[0] <= cutoff:
                message_times.popleft()
            if len(message_times) >= settings.websocket_message_rate_limit:
                logger.warning(
                    "workspace_websocket_rate_limited", extra={"reason": "messages"}
                )
                await websocket.close(code=4429)
                return
            message_times.append(now)

            if now - last_validation >= settings.websocket_revalidation_seconds:
                if not _same_access(
                    factory,
                    websocket.cookies.get(settings.session_cookie_name),
                    authenticated,
                    workspace_id,
                ):
                    logger.warning(
                        "workspace_websocket_closed", extra={"reason": "access_revoked"}
                    )
                    await websocket.close(code=4401)
                    return
                last_validation = now

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
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(workspace_id, connection_id)


def _validate_access(
    factory: sessionmaker[Session], raw_token: str | None
) -> AuthenticatedUser | None:
    with session_scope(factory) as session:
        authenticated = authenticated_user(session, raw_token)
        if authenticated is None or authenticated.active_workspace_id is None:
            return None
        if (
            membership_for_user(
                session, authenticated.id, authenticated.active_workspace_id
            )
            is None
        ):
            return None
        return authenticated


def _same_access(
    factory: sessionmaker[Session],
    raw_token: str | None,
    original: AuthenticatedUser,
    workspace_id: int,
) -> bool:
    current = _validate_access(factory, raw_token)
    return (
        current is not None
        and current.id == original.id
        and current.session_id == original.session_id
        and current.active_workspace_id == workspace_id
    )


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
    except (json.JSONDecodeError, ValidationError):
        return None
