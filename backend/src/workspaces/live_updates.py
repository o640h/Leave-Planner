"""Post-commit invalidations and ephemeral workspace pointer fan-out."""

from __future__ import annotations

import asyncio
import secrets
import zlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from fastapi import WebSocket
from sqlalchemy.orm import Session

PENDING_INVALIDATIONS_KEY = "pending_workspace_invalidations"
POINTER_COLOUR_COUNT = 8


class WorkspaceConnectionLimit(Exception):
    """The account already owns the permitted number of live sockets."""


@dataclass(frozen=True, slots=True)
class WorkspaceInvalidation:
    workspace_id: int
    revision: int
    scopes: frozenset[str]


def queue_invalidation(
    session: Session, *, workspace_id: int, revision: int, scopes: Iterable[str]
) -> None:
    """Coalesce invalidations until the surrounding transaction commits."""
    queued = session.info.setdefault(PENDING_INVALIDATIONS_KEY, {})
    existing = queued.get(workspace_id)
    combined = frozenset(scopes)
    if existing is not None:
        combined |= existing.scopes
    queued[workspace_id] = WorkspaceInvalidation(workspace_id, revision, combined)


def take_invalidations(session: Session) -> tuple[WorkspaceInvalidation, ...]:
    queued = session.info.pop(PENDING_INVALIDATIONS_KEY, {})
    return tuple(queued.values())


@dataclass(slots=True)
class WorkspaceConnection:
    connection_id: str
    websocket: WebSocket
    user_id: int
    session_id: int
    label: str
    colour_index: int
    view: str | None = None
    pointer_visible: bool = False
    pointer_x: float | None = None
    pointer_y: float | None = None
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class WorkspaceUpdateHub:
    """Process-local fan-out for the deployment's single application worker."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._connections: dict[int, dict[str, WorkspaceConnection]] = {}

    async def connect(
        self,
        workspace_id: int,
        websocket: WebSocket,
        *,
        user_id: int,
        public_id: str,
        display_name: str,
        session_id: int = 0,
        max_connections_for_user: int | None = None,
    ) -> str:
        await websocket.accept()
        if (
            max_connections_for_user is not None
            and self.connection_count_for_user(user_id) >= max_connections_for_user
        ):
            await websocket.close(code=4429)
            raise WorkspaceConnectionLimit
        workspace_connections = self._connections.setdefault(workspace_id, {})
        same_user = next(
            (
                connection
                for connection in workspace_connections.values()
                if connection.user_id == user_id
            ),
            None,
        )
        if same_user is not None:
            colour_index = same_user.colour_index
        else:
            preferred_colour = zlib.crc32(public_id.encode("utf-8")) % POINTER_COLOUR_COUNT
            used_colours = {
                connection.colour_index for connection in workspace_connections.values()
            }
            colour_index = next(
                (
                    (preferred_colour + offset) % POINTER_COLOUR_COUNT
                    for offset in range(POINTER_COLOUR_COUNT)
                    if (preferred_colour + offset) % POINTER_COLOUR_COUNT not in used_colours
                ),
                preferred_colour,
            )
        connection_id = secrets.token_urlsafe(9)
        workspace_connections[connection_id] = WorkspaceConnection(
            connection_id=connection_id,
            websocket=websocket,
            user_id=user_id,
            session_id=session_id,
            label=_pointer_label(display_name),
            colour_index=colour_index,
        )
        return connection_id

    def connection_count_for_user(self, user_id: int) -> int:
        return sum(
            connection.user_id == user_id
            for connections in self._connections.values()
            for connection in connections.values()
        )

    async def close_session(self, session_id: int, *, code: int = 4401) -> None:
        await self._close_matching(
            lambda connection: connection.session_id == session_id,
            code=code,
        )

    async def close_user(self, user_id: int, *, code: int = 4401) -> None:
        await self._close_matching(
            lambda connection: connection.user_id == user_id,
            code=code,
        )

    def close_session_soon(self, session_id: int, *, code: int = 4401) -> None:
        asyncio.run_coroutine_threadsafe(self.close_session(session_id, code=code), self._loop)

    def close_user_soon(self, user_id: int, *, code: int = 4401) -> None:
        asyncio.run_coroutine_threadsafe(self.close_user(user_id, code=code), self._loop)

    async def disconnect(self, workspace_id: int, connection_id: str) -> None:
        connections = self._connections.get(workspace_id)
        if connections is None:
            return
        connection = connections.pop(connection_id, None)
        if connection is None:
            return
        if connection.pointer_visible:
            await self._send_to_view(
                workspace_id,
                connection.view,
                {"type": "pointer_removed", "connection_id": connection_id},
            )
        if not connections:
            self._connections.pop(workspace_id, None)

    async def set_view(self, workspace_id: int, connection_id: str, view: str | None) -> None:
        connection = self._connection(workspace_id, connection_id)
        if connection is None or connection.view == view:
            return
        if connection.pointer_visible:
            await self._send_to_view(
                workspace_id,
                connection.view,
                {"type": "pointer_removed", "connection_id": connection_id},
            )
        connection.view = view
        connection.pointer_visible = False
        connection.pointer_x = None
        connection.pointer_y = None
        if view is None:
            return
        for existing in tuple(self._connections.get(workspace_id, {}).values()):
            if (
                existing.connection_id == connection_id
                or existing.view != view
                or not existing.pointer_visible
                or existing.pointer_x is None
                or existing.pointer_y is None
            ):
                continue
            await self._send(
                workspace_id,
                connection,
                self._pointer_payload(existing, view, existing.pointer_x, existing.pointer_y),
            )

    async def move_pointer(
        self,
        workspace_id: int,
        connection_id: str,
        *,
        view: str,
        x: float,
        y: float,
    ) -> None:
        connection = self._connection(workspace_id, connection_id)
        if connection is None or connection.view != view:
            return
        connection.pointer_visible = True
        connection.pointer_x = x
        connection.pointer_y = y
        await self._send_to_view(
            workspace_id,
            view,
            self._pointer_payload(connection, view, x, y),
            exclude=connection_id,
        )

    async def hide_pointer(self, workspace_id: int, connection_id: str) -> None:
        connection = self._connection(workspace_id, connection_id)
        if connection is None or not connection.pointer_visible:
            return
        connection.pointer_visible = False
        connection.pointer_x = None
        connection.pointer_y = None
        await self._send_to_view(
            workspace_id,
            connection.view,
            {"type": "pointer_removed", "connection_id": connection_id},
        )

    async def publish(self, invalidations: tuple[WorkspaceInvalidation, ...]) -> None:
        for invalidation in invalidations:
            await self._send_to_workspace(
                invalidation.workspace_id,
                {
                    "type": "workspace_invalidated",
                    "revision": invalidation.revision,
                    "scopes": sorted(invalidation.scopes),
                },
            )
            if "workspace-context" in invalidation.scopes:
                await self._reconnect_workspace(invalidation.workspace_id)

    def publish_after_commit(self, invalidations: tuple[WorkspaceInvalidation, ...]) -> None:
        if invalidations and self._connections:
            asyncio.run_coroutine_threadsafe(self.publish(invalidations), self._loop)

    def _connection(self, workspace_id: int, connection_id: str) -> WorkspaceConnection | None:
        return self._connections.get(workspace_id, {}).get(connection_id)

    @staticmethod
    def _pointer_payload(
        connection: WorkspaceConnection, view: str, x: float, y: float
    ) -> dict[str, object]:
        return {
            "type": "pointer_updated",
            "connection_id": connection.connection_id,
            "label": connection.label,
            "colour_index": connection.colour_index,
            "view": view,
            "x": x,
            "y": y,
        }

    async def _send_to_view(
        self,
        workspace_id: int,
        view: str | None,
        payload: dict[str, object],
        *,
        exclude: str | None = None,
    ) -> None:
        if view is None:
            return
        recipients = tuple(self._connections.get(workspace_id, {}).values())
        for connection in recipients:
            if connection.connection_id == exclude or connection.view != view:
                continue
            await self._send(workspace_id, connection, payload)

    async def _send_to_workspace(self, workspace_id: int, payload: dict[str, object]) -> None:
        for connection in tuple(self._connections.get(workspace_id, {}).values()):
            await self._send(workspace_id, connection, payload)

    async def _send(
        self,
        workspace_id: int,
        connection: WorkspaceConnection,
        payload: dict[str, object],
    ) -> None:
        try:
            async with connection.send_lock:
                await connection.websocket.send_json(payload)
        except RuntimeError:
            await self.disconnect(workspace_id, connection.connection_id)

    async def _reconnect_workspace(self, workspace_id: int) -> None:
        """Force immediate access revalidation after membership or workspace changes."""
        connections = tuple(self._connections.get(workspace_id, {}).values())
        for connection in connections:
            try:
                await connection.websocket.close(code=4409)
            finally:
                await self.disconnect(workspace_id, connection.connection_id)

    async def _close_matching(
        self, predicate: Callable[[WorkspaceConnection], bool], *, code: int
    ) -> None:
        matches = [
            (workspace_id, connection)
            for workspace_id, connections in self._connections.items()
            for connection in connections.values()
            if predicate(connection)
        ]
        for workspace_id, connection in matches:
            try:
                await connection.websocket.close(code=code)
            finally:
                await self.disconnect(workspace_id, connection.connection_id)


def _pointer_label(display_name: str) -> str:
    return next((character.upper() for character in display_name if character.isalnum()), "?")
