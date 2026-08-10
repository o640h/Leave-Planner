"""Add holiday, adjustment, and flexible-hour storage.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist workbook flexible hours, holiday data, and year adjustments."""

    op.add_column(
        "job_plan_versions",
        sa.Column(
            "additional_dcc_hours",
            sa.Numeric(9, 3),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "job_plan_versions",
        sa.Column(
            "additional_spa_hours",
            sa.Numeric(9, 3),
            server_default="0",
            nullable=False,
        ),
    )

    op.create_table(
        "holiday_calendar_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("source_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
    )
    op.create_table(
        "holiday_calendar_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "calendar_version_id",
            sa.Integer(),
            sa.ForeignKey("holiday_calendar_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=False, server_default=""),
        sa.UniqueConstraint(
            "calendar_version_id",
            "holiday_date",
            name="uq_holiday_calendar_event_date",
        ),
    )
    op.create_table(
        "holiday_corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("replacement_name", sa.String(length=160), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("retired_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_holiday_corrections_active_date",
        "holiday_corrections",
        ["holiday_date", "retired_at"],
    )
    op.create_table(
        "public_holiday_treatments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "leave_year_id",
            sa.Integer(),
            sa.ForeignKey("leave_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("basis", sa.String(length=30), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("worked_date", sa.Date(), nullable=True),
        sa.UniqueConstraint(
            "leave_year_id",
            "holiday_date",
            name="uq_public_holiday_treatment_date",
        ),
    )
    op.create_table(
        "leave_year_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "leave_year_id",
            sa.Integer(),
            sa.ForeignKey("leave_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("dcc_hours", sa.Numeric(12, 6), nullable=False),
        sa.Column("spa_hours", sa.Numeric(12, 6), nullable=False),
        sa.Column("other_hours", sa.Numeric(12, 6), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("source", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind = 'carry_forward'",
            name="ck_leave_year_adjustment_kind",
        ),
    )
    op.create_index(
        "ix_leave_year_adjustments_leave_year_id",
        "leave_year_adjustments",
        ["leave_year_id"],
    )


def downgrade() -> None:
    """Remove holiday, adjustment, and flexible-hour storage."""

    op.drop_index(
        "ix_leave_year_adjustments_leave_year_id",
        table_name="leave_year_adjustments",
    )
    op.drop_table("leave_year_adjustments")
    op.drop_table("public_holiday_treatments")
    op.drop_index(
        "ix_holiday_corrections_active_date",
        table_name="holiday_corrections",
    )
    op.drop_table("holiday_corrections")
    op.drop_table("holiday_calendar_events")
    op.drop_table("holiday_calendar_versions")
    op.drop_column("job_plan_versions", "additional_spa_hours")
    op.drop_column("job_plan_versions", "additional_dcc_hours")
