"""FastAPI routes for annual-entitlement setup."""

from typing import Annotated

from fastapi import APIRouter, Query

from dependencies import DatabaseSession

from . import service
from .schemas import (
    EntitlementApply,
    EntitlementRecommendation,
    EntitlementWorkspace,
)

router = APIRouter(
    prefix=("/api/consultants/{consultant_id}/leave-years/{leave_year_id}/entitlement"),
    tags=["annual entitlement"],
)


@router.get("", response_model=EntitlementWorkspace)
def get_entitlement(
    consultant_id: int,
    leave_year_id: int,
    session: DatabaseSession,
) -> EntitlementWorkspace:
    return service.get_workspace(
        session,
        consultant_id,
        leave_year_id,
    )


@router.post("/preview", response_model=EntitlementRecommendation)
def preview_entitlement(
    consultant_id: int,
    leave_year_id: int,
    session: DatabaseSession,
    seven_years_or_more: Annotated[bool, Query()],
) -> EntitlementRecommendation:
    return service.calculate_recommendation(
        session,
        consultant_id,
        leave_year_id,
        seven_years_or_more=seven_years_or_more,
    )


@router.put("", response_model=EntitlementWorkspace)
def apply_entitlement(
    consultant_id: int,
    leave_year_id: int,
    details: EntitlementApply,
    session: DatabaseSession,
) -> EntitlementWorkspace:
    return service.apply_entitlement(
        session,
        consultant_id,
        leave_year_id,
        details,
    )


@router.post("/refresh", response_model=EntitlementWorkspace)
def refresh_entitlement(
    consultant_id: int,
    leave_year_id: int,
    session: DatabaseSession,
) -> EntitlementWorkspace:
    return service.refresh_entitlement(
        session,
        consultant_id,
        leave_year_id,
    )
