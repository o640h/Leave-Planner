"""Authenticated endpoints for the restricted Member workspace."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from dependencies import DatabaseSession
from workspaces.dependencies import require_member_workspace_request
from workspaces.service import WorkspaceAccess

from . import service
from .schemas import MemberWallchartRead, MemberWorkspaceRead

router = APIRouter(prefix="/api/member", tags=["member-workspace"])
MemberAccess = Annotated[WorkspaceAccess, Depends(require_member_workspace_request)]


@router.get("/workspace", response_model=MemberWorkspaceRead)
def read_workspace(
    session: DatabaseSession,
    access: MemberAccess,
    leave_year_id: int | None = Query(default=None),
) -> MemberWorkspaceRead:
    return service.workspace(session, access, leave_year_id)


@router.get("/wallchart", response_model=MemberWallchartRead)
def read_wallchart(
    session: DatabaseSession,
    month: date,
    access: MemberAccess,
) -> MemberWallchartRead:
    return service.wallchart(session, access, month)
