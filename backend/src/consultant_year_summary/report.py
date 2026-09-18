"""Create a printer-friendly consultant leave-log PDF."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from html import escape
from io import BytesIO
from typing import Any

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.enums import TA_RIGHT  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from leave_bookings.schemas import ActivityHoursRead

from .schemas import LeaveLogEntryRead

PAGE_WIDTH, PAGE_HEIGHT = A4
CONTENT_MARGIN = 17 * mm
TEXT = colors.HexColor("#27324d")
MUTED = colors.HexColor("#6d7588")
ACCENT = colors.HexColor("#627da5")
LINE = colors.HexColor("#d9dee7")
HEADER = colors.HexColor("#edf1f6")
ALTERNATE = colors.HexColor("#f8f9fb")
STATUS_COLOURS = {
    "requested": colors.HexColor("#377f97"),
    "approved": colors.HexColor("#39775d"),
    "public_holiday": colors.HexColor("#9a743d"),
    "cancelled": MUTED,
}
MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def _date(value: date) -> str:
    return f"{value.day} {MONTHS[value.month - 1]} {value.year}"


def _hours(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"))
    return format(rounded, "f").rstrip("0").rstrip(".") or "0"


def _state(value: str) -> str:
    return value.replace("_", " ").title()


def _filename_part(value: str) -> str:
    cleaned = "_".join(
        "".join(character for character in part if character.isascii() and character.isalnum())
        for part in value.split()
    )
    return cleaned or "Consultant"


def leave_log_filename(consultant_name: str, start_date: date, end_date: date) -> str:
    return (
        f"{_filename_part(consultant_name)}_Leave_Log_"
        f"{start_date.isoformat()}_to_{end_date.isoformat()}.pdf"
    )


def render_leave_log_pdf(
    *,
    consultant_name: str,
    post_title: str | None,
    leave_year_start: date,
    leave_year_end: date,
    entries: tuple[LeaveLogEntryRead, ...],
    leave_remaining: ActivityHoursRead | None,
    generated_at: datetime | None = None,
) -> bytes:
    """Render one complete, multipage leave log entirely in memory."""

    created = generated_at or datetime.now().astimezone()
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=CONTENT_MARGIN,
        leftMargin=CONTENT_MARGIN,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=f"{consultant_name} Leave Log",
        author="Leave Planner",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "LeaveLogTitle",
        parent=styles["Title"],
        fontName="Helvetica",
        fontSize=19,
        leading=23,
        textColor=TEXT,
        spaceAfter=3 * mm,
    )
    name_style = ParagraphStyle(
        "ConsultantName",
        parent=styles["Heading2"],
        fontName="Helvetica",
        fontSize=12,
        leading=15,
        textColor=TEXT,
        spaceAfter=1 * mm,
    )
    meta_style = ParagraphStyle(
        "ReportMeta",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=MUTED,
    )
    cell_style = ParagraphStyle(
        "ReportCell",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=TEXT,
    )
    number_style = ParagraphStyle(
        "ReportNumber",
        parent=cell_style,
        alignment=TA_RIGHT,
    )
    header_style = ParagraphStyle(
        "ReportHeader",
        parent=cell_style,
        fontName="Helvetica-Bold",
        fontSize=7,
        textColor=TEXT,
    )

    story: list[Any] = [
        Paragraph("Consultant Leave Log", title_style),
        Paragraph(escape(consultant_name), name_style),
    ]
    if post_title:
        story.append(Paragraph(escape(post_title), meta_style))
    story.extend(
        [
            Spacer(1, 2 * mm),
            Table(
                [
                    [
                        Paragraph("Leave Year", header_style),
                        Paragraph(
                            f"{_date(leave_year_start)} - {_date(leave_year_end)}",
                            cell_style,
                        ),
                        Paragraph("Generated", header_style),
                        Paragraph(f"{_date(created.date())}, {created:%H:%M}", cell_style),
                    ]
                ],
                colWidths=(21 * mm, 67 * mm, 18 * mm, 70 * mm),
                hAlign="CENTER",
                style=TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("BACKGROUND", (0, 0), (-1, -1), HEADER),
                        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                        ("INNERGRID", (0, 0), (-1, -1), 0.25, LINE),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                ),
            ),
            Spacer(1, 5 * mm),
        ]
    )

    table_data: list[list[Any]] = [
        [
            Paragraph("Date", header_style),
            Paragraph("Entry", header_style),
            Paragraph("Status", header_style),
            Paragraph("DCC", header_style),
            Paragraph("SPA", header_style),
            Paragraph("Total", header_style),
        ]
    ]
    for entry in entries:
        date_text = _date(entry.start_date)
        if entry.end_date != entry.start_date:
            date_text = f"{date_text} - {_date(entry.end_date)}"
        status_style = ParagraphStyle(
            f"Status-{entry.state}",
            parent=cell_style,
            textColor=STATUS_COLOURS.get(entry.state, MUTED),
        )
        table_data.append(
            [
                Paragraph(date_text, cell_style),
                Paragraph(escape(entry.description).replace("\n", "<br/>"), cell_style),
                Paragraph(_state(entry.state), status_style),
                Paragraph(_hours(entry.amounts.dcc_hours), number_style),
                Paragraph(_hours(entry.amounts.spa_hours), number_style),
                Paragraph(_hours(entry.amounts.total_hours), number_style),
            ]
        )

    if entries:
        table = Table(
            table_data,
            colWidths=(30 * mm, 67 * mm, 25 * mm, 17 * mm, 17 * mm, 20 * mm),
            repeatRows=1,
            hAlign="CENTER",
        )
        commands: list[tuple[Any, ...]] = [
            ("BACKGROUND", (0, 0), (-1, 0), HEADER),
            ("LINEBELOW", (0, 0), (-1, 0), 0.75, ACCENT),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, 0), 7),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
            ("TOPPADDING", (0, 1), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ]
        for row_number in range(2, len(table_data), 2):
            commands.append(("BACKGROUND", (0, row_number), (-1, row_number), ALTERNATE))
        table.setStyle(TableStyle(commands))
        story.append(table)
    else:
        story.append(Paragraph("No leave has been logged for this leave year.", cell_style))

    dcc_total = sum((entry.amounts.dcc_hours for entry in entries), Decimal("0"))
    spa_total = sum((entry.amounts.spa_hours for entry in entries), Decimal("0"))
    total = sum((entry.amounts.total_hours for entry in entries), Decimal("0"))
    totals = Table(
        [
            [
                Paragraph("Leave Log Totals", header_style),
                Paragraph(f"DCC&nbsp;&nbsp; {_hours(dcc_total)}h", number_style),
                Paragraph(f"SPA&nbsp;&nbsp; {_hours(spa_total)}h", number_style),
                Paragraph(f"Total&nbsp;&nbsp; {_hours(total)}h", number_style),
            ]
        ],
        colWidths=(88 * mm, 27 * mm, 27 * mm, 34 * mm),
        hAlign="CENTER",
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HEADER),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("LINEABOVE", (0, 0), (-1, 0), 0.75, ACCENT),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        ),
    )
    if leave_remaining is None:
        remaining_data = [
            [
                Paragraph("Leave Remaining", header_style),
                Paragraph("Not available until annual entitlement is applied.", cell_style),
                "",
                "",
            ]
        ]
    else:
        remaining_data = [
            [
                Paragraph("Leave Remaining", header_style),
                Paragraph(f"DCC&nbsp;&nbsp; {_hours(leave_remaining.dcc_hours)}h", number_style),
                Paragraph(f"SPA&nbsp;&nbsp; {_hours(leave_remaining.spa_hours)}h", number_style),
                Paragraph(
                    f"Total&nbsp;&nbsp; {_hours(leave_remaining.total_hours)}h",
                    number_style,
                ),
            ]
        ]
    remaining_commands: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, -1), ALTERNATE),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]
    if leave_remaining is None:
        remaining_commands.append(("SPAN", (1, 0), (-1, 0)))
    remaining = Table(
        remaining_data,
        colWidths=(88 * mm, 27 * mm, 27 * mm, 34 * mm),
        hAlign="CENTER",
        style=TableStyle(remaining_commands),
    )
    story.extend([Spacer(1, 5 * mm), KeepTogether([totals, Spacer(1, 2 * mm), remaining])])

    def add_page_details(canvas: Canvas, document_template: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(CONTENT_MARGIN, 11 * mm, PAGE_WIDTH - CONTENT_MARGIN, 11 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(CONTENT_MARGIN, 7 * mm, "Generated by Leave Planner")
        canvas.drawRightString(
            PAGE_WIDTH - CONTENT_MARGIN,
            7 * mm,
            f"Page {document_template.page}",
        )
        canvas.restoreState()

    document.build(story, onFirstPage=add_page_details, onLaterPages=add_page_details)
    return output.getvalue()
