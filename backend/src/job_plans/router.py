"""FastAPI routes for consultant job plans."""

from fastapi import APIRouter, status

from dependencies import DatabaseSession
from removal import RemovalCommand, RemovalImpact, RemovalResult

from . import service
from .persistence import JobPlanRecord
from .schemas import (
    JobPlanCreate,
    JobPlanFields,
    JobPlanPreview,
    JobPlanRead,
    JobPlanUpdate,
    JobPlanUpdateImpact,
)

router = APIRouter(
    prefix=("/api/consultants/{consultant_id}/leave-years/{leave_year_id}/job-plans"),
    tags=["job plans"],
)


@router.get("", response_model=list[JobPlanRead])
def list_job_plans(
    consultant_id: int,
    leave_year_id: int,
    session: DatabaseSession,
) -> tuple[JobPlanRecord, ...]:
    return service.list_job_plans(
        session,
        consultant_id,
        leave_year_id,
    )


@router.post("/preview", response_model=JobPlanPreview)
def preview_job_plan(
    consultant_id: int,
    leave_year_id: int,
    details: JobPlanFields,
    session: DatabaseSession,
) -> JobPlanPreview:
    return service.preview_job_plan(
        session,
        consultant_id,
        leave_year_id,
        details,
    )


@router.post(
    "",
    response_model=JobPlanRead,
    status_code=status.HTTP_201_CREATED,
)
def create_job_plan(
    consultant_id: int,
    leave_year_id: int,
    details: JobPlanCreate,
    session: DatabaseSession,
) -> JobPlanRecord:
    return service.create_job_plan(
        session,
        consultant_id,
        leave_year_id,
        details,
    )


@router.post("/{job_plan_id}/update-impact", response_model=JobPlanUpdateImpact)
def update_impact(
    consultant_id: int,
    leave_year_id: int,
    job_plan_id: int,
    details: JobPlanUpdate,
    session: DatabaseSession,
) -> JobPlanUpdateImpact:
    return service.update_impact(
        session,
        consultant_id,
        leave_year_id,
        job_plan_id,
        details,
    )


@router.put("/{job_plan_id}", response_model=JobPlanRead)
def update_job_plan(
    consultant_id: int,
    leave_year_id: int,
    job_plan_id: int,
    details: JobPlanUpdate,
    session: DatabaseSession,
    regenerate_booking_days: bool = False,
) -> JobPlanRecord:
    return service.update_job_plan(
        session,
        consultant_id,
        leave_year_id,
        job_plan_id,
        details,
        regenerate_booking_days=regenerate_booking_days,
    )


@router.get("/{job_plan_id}/removal-impact", response_model=RemovalImpact)
def removal_impact(
    consultant_id: int,
    leave_year_id: int,
    job_plan_id: int,
    session: DatabaseSession,
) -> RemovalImpact:
    return service.removal_impact(
        session,
        consultant_id,
        leave_year_id,
        job_plan_id,
    )


@router.post("/{job_plan_id}/remove", response_model=RemovalResult)
def remove_job_plan(
    consultant_id: int,
    leave_year_id: int,
    job_plan_id: int,
    command: RemovalCommand,
    session: DatabaseSession,
) -> RemovalResult:
    return service.remove_job_plan(
        session,
        consultant_id,
        leave_year_id,
        job_plan_id,
        command,
    )
