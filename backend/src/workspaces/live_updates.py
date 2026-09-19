"""Post-commit workspace invalidations and connected WebSocket clients."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass

from fastapi import WebSocket
from sqlalchemy.orm import Session

PENDING_INVALIDATIONS_KEY = "pending_workspace_invalidations"


@dataclass(frozen=True, slots=True)
class WorkspaceInvalidation:
    workspace_id: int
    revision: int
    scopes: frozenset[str]


def queue_invalidation(
    session: Session,
    *,
    workspace_id: int,
    revision: int,
    scopes: Iterable[str],
) -> None:
    """Coalesce invalidations until the surrounding transaction commits."""

    queued = session.info.setdefault(PENDING_INVALIDATIONS_KEY, {})
    existing = queued.get(workspace_id)
    combined = frozenset(scopes)
    if existing is not None:
        combined |= existing.scopes
    queued[workspace_id] = WorkspaceInvalidation(
        workspace_id=workspace_id,
        revision=revision,
        scopes=combined,
    )


def take_invalidations(session: Session) -> tuple[WorkspaceInvalidation, ...]:
    queued = session.info.pop(PENDING_INVALIDATIONS_KEY, {})
    return tuple(queued.values())


class WorkspaceUpdateHub:
    """Process-local fan-out for the deployment's single application worker."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._connections: dict[int, set[WebSocket]] = {}

    async def connect(self, workspace_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(workspace_id, set()).add(websocket)

    def disconnect(self, workspace_id: int, websocket: WebSocket) -> None:
        connections = self._connections.get(workspace_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(workspace_id, None)

    async def publish(self, invalidations: tuple[WorkspaceInvalidation, ...]) -> None:
        for invalidation in invalidations:
            payload = {
                "type": "workspace_invalidated",
                "revision": invalidation.revision,
                "scopes": sorted(invalidation.scopes),
            }
            stale: list[WebSocket] = []
            for websocket in tuple(self._connections.get(invalidation.workspace_id, ())):
                try:
                    await websocket.send_json(payload)
                except RuntimeError:
                    stale.append(websocket)
            for websocket in stale:
                self.disconnect(invalidation.workspace_id, websocket)

    def publish_after_commit(
        self, invalidations: tuple[WorkspaceInvalidation, ...]
    ) -> None:
        if not invalidations or not self._connections:
            return
        asyncio.run_coroutine_threadsafe(self.publish(invalidations), self._loop)
