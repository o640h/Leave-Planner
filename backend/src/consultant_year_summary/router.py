"""Consultant-year summary route."""

from fastapi import APIRouter, Response

from dependencies import DatabaseSession

from .report import leave_log_filename, render_leave_log_pdf
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


@router.get("/leave-log.pdf")
def export_leave_log(
    consultant_id: int,
    leave_year_id: int,
    session: DatabaseSession,
) -> Response:
    summary = get_summary(session, consultant_id, leave_year_id)
    filename = leave_log_filename(
        summary.consultant.name,
        summary.leave_year.start_date,
        summary.leave_year.end_date,
    )
    content = render_leave_log_pdf(
        consultant_name=summary.consultant.name,
        post_title=summary.consultant.post_title,
        leave_year_start=summary.leave_year.start_date,
        leave_year_end=summary.leave_year.end_date,
        entries=summary.leave_log,
    )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
