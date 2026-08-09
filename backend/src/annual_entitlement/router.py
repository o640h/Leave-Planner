"""FastAPI routes for annual-entitlement setup."""

from datetime import date
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
    consultant_appointment_date: Annotated[date, Query()],
    consultant_service_start_date: Annotated[date, Query()],
) -> EntitlementRecommendation:
    return service.calculate_recommendation(
        session,
        consultant_id,
        leave_year_id,
        consultant_appointment_date=consultant_appointment_date,
        consultant_service_start_date=(consultant_service_start_date),
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
