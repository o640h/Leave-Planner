"""Create leave bookings and calculated day snapshots.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leave_bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "leave_year_id",
            sa.Integer(),
            sa.ForeignKey("leave_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False
        ),
        sa.CheckConstraint("end_date >= start_date", name="ck_leave_booking_dates"),
        sa.CheckConstraint(
            "state IN ('planned', 'approved', 'taken', 'cancelled')",
            name="ck_leave_booking_state",
        ),
    )
    op.create_index("ix_leave_bookings_leave_year_id", "leave_bookings", ["leave_year_id"])

    op.create_table(
        "leave_booking_days",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "booking_id",
            sa.Integer(),
            sa.ForeignKey("leave_bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_plan_id",
            sa.Integer(),
            sa.ForeignKey("job_plan_versions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("leave_date", sa.Date(), nullable=False),
        sa.Column("standard_dcc_hours", sa.Numeric(12, 6), nullable=False),
        sa.Column("standard_spa_hours", sa.Numeric(12, 6), nullable=False),
        sa.Column("standard_other_hours", sa.Numeric(12, 6), nullable=False),
        sa.Column("deduction_dcc_hours", sa.Numeric(12, 6), nullable=False),
        sa.Column("deduction_spa_hours", sa.Numeric(12, 6), nullable=False),
        sa.Column("deduction_other_hours", sa.Numeric(12, 6), nullable=False),
        sa.Column("override_reason", sa.String(length=500), nullable=True),
        sa.UniqueConstraint("booking_id", "leave_date", name="uq_leave_booking_day_date"),
        sa.CheckConstraint(
            "standard_dcc_hours >= 0 AND standard_spa_hours >= 0 "
            "AND standard_other_hours >= 0",
            name="ck_leave_booking_day_standard_hours",
        ),
        sa.CheckConstraint(
            "deduction_dcc_hours >= 0 AND deduction_spa_hours >= 0 "
            "AND deduction_other_hours >= 0",
            name="ck_leave_booking_day_deduction_hours",
        ),
    )
    op.create_index("ix_leave_booking_days_booking_id", "leave_booking_days", ["booking_id"])
    op.create_index("ix_leave_booking_days_job_plan_id", "leave_booking_days", ["job_plan_id"])


def downgrade() -> None:
    op.drop_index("ix_leave_booking_days_job_plan_id", table_name="leave_booking_days")
    op.drop_index("ix_leave_booking_days_booking_id", table_name="leave_booking_days")
    op.drop_table("leave_booking_days")
    op.drop_index("ix_leave_bookings_leave_year_id", table_name="leave_bookings")
    op.drop_table("leave_bookings")

