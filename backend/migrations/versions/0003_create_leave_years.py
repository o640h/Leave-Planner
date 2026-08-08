"""Create leave years and audit events.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add consultant leave years and their change history."""

    op.create_table(
        "leave_years",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "consultant_id",
            sa.Integer(),
            sa.ForeignKey("consultants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("employment_start", sa.Date(), nullable=True),
        sa.Column("employment_end", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "end_date >= start_date",
            name="ck_leave_year_dates",
        ),
        sa.CheckConstraint(
            """
            employment_start IS NULL
            OR (
                employment_start >= start_date
                AND employment_start <= end_date
            )
            """,
            name="ck_leave_year_employment_start",
        ),
        sa.CheckConstraint(
            """
            employment_end IS NULL
            OR (
                employment_end >= start_date
                AND employment_end <= end_date
            )
            """,
            name="ck_leave_year_employment_end",
        ),
        sa.CheckConstraint(
            """
            employment_start IS NULL
            OR employment_end IS NULL
            OR employment_end >= employment_start
            """,
            name="ck_leave_year_employment_dates",
        ),
    )

    op.create_index(
        "ix_leave_years_consultant_id",
        "leave_years",
        ["consultant_id"],
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "consultant_id",
            sa.Integer(),
            sa.ForeignKey("consultants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_audit_events_consultant_id",
        "audit_events",
        ["consultant_id"],
    )


def downgrade() -> None:
    """Remove leave-year and audit-event storage."""

    op.drop_index("ix_audit_events_consultant_id", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_leave_years_consultant_id", table_name="leave_years")
    op.drop_table("leave_years")
