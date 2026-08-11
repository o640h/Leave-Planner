"""Consultant-year summary route."""

from fastapi import APIRouter

from dependencies import DatabaseSession

from .schemas import ConsultantYearSummaryRead
from .service import get_summary

router = APIRouter(
    prefix="/api/consultants/{consultant_id}/leave-years/{leave_year_id}",
    tags=["consultant year summary"],
)


@router.get("/summary", response_model=ConsultantYearSummaryRead)
def read_summary(
    consultant_id: int, leave_year_id: int, session: DatabaseSession
) -> ConsultantYearSummaryRead:
    return get_summary(session, consultant_id, leave_year_id)
