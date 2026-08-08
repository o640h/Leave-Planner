"""Create effective-dated job plans.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add job-plan versions and their weekday patterns."""

    op.create_table(
        "job_plan_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "leave_year_id",
            sa.Integer(),
            sa.ForeignKey("leave_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date(), nullable=False),
        sa.Column("cycle_anchor_date", sa.Date(), nullable=False),
        sa.Column("week_count", sa.Integer(), nullable=False),
        sa.Column("contracted_pas", sa.Numeric(9, 3), nullable=False),
        sa.Column("dcc_pas", sa.Numeric(9, 3), nullable=False),
        sa.Column("spa_pas", sa.Numeric(9, 3), nullable=False),
        sa.Column("other_pas", sa.Numeric(9, 3), nullable=False),
        sa.Column("hours_per_pa", sa.Numeric(9, 3), nullable=False),
        sa.Column(
            "reconciliation_override_reason",
            sa.String(length=500),
            nullable=True,
        ),
        sa.CheckConstraint(
            "effective_until > effective_from",
            name="ck_job_plan_effective_dates",
        ),
        sa.CheckConstraint(
            "cycle_anchor_date <= effective_from",
            name="ck_job_plan_anchor_date",
        ),
        sa.CheckConstraint(
            "week_count >= 1",
            name="ck_job_plan_week_count",
        ),
        sa.CheckConstraint(
            "contracted_pas >= 0",
            name="ck_job_plan_contracted_pas",
        ),
        sa.CheckConstraint("dcc_pas >= 0", name="ck_job_plan_dcc_pas"),
        sa.CheckConstraint("spa_pas >= 0", name="ck_job_plan_spa_pas"),
        sa.CheckConstraint("other_pas >= 0", name="ck_job_plan_other_pas"),
        sa.CheckConstraint(
            "hours_per_pa > 0",
            name="ck_job_plan_hours_per_pa",
        ),
    )

    op.create_index(
        "ix_job_plan_versions_leave_year_id",
        "job_plan_versions",
        ["leave_year_id"],
    )

    op.create_table(
        "job_plan_days",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "job_plan_id",
            sa.Integer(),
            sa.ForeignKey("job_plan_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cycle_week", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("dcc_hours", sa.Numeric(9, 3), nullable=False),
        sa.Column("spa_hours", sa.Numeric(9, 3), nullable=False),
        sa.Column("other_hours", sa.Numeric(9, 3), nullable=False),
        sa.CheckConstraint(
            "cycle_week >= 1",
            name="ck_job_plan_day_cycle_week",
        ),
        sa.CheckConstraint(
            "weekday >= 0 AND weekday <= 6",
            name="ck_job_plan_day_weekday",
        ),
        sa.CheckConstraint(
            "dcc_hours >= 0",
            name="ck_job_plan_day_dcc_hours",
        ),
        sa.CheckConstraint(
            "spa_hours >= 0",
            name="ck_job_plan_day_spa_hours",
        ),
        sa.CheckConstraint(
            "other_hours >= 0",
            name="ck_job_plan_day_other_hours",
        ),
        sa.UniqueConstraint(
            "job_plan_id",
            "cycle_week",
            "weekday",
            name="uq_job_plan_day_position",
        ),
    )

    op.create_index(
        "ix_job_plan_days_job_plan_id",
        "job_plan_days",
        ["job_plan_id"],
    )


def downgrade() -> None:
    """Remove job-plan storage."""

    op.drop_index("ix_job_plan_days_job_plan_id", table_name="job_plan_days")
    op.drop_table("job_plan_days")

    op.drop_index(
        "ix_job_plan_versions_leave_year_id",
        table_name="job_plan_versions",
    )
    op.drop_table("job_plan_versions")
