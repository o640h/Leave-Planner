"""Create entitlement recommendation and application storage.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add immutable recommendations and applied opening values."""

    op.create_table(
        "entitlement_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "leave_year_id",
            sa.Integer(),
            sa.ForeignKey("leave_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("inputs_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("trace_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_entitlement_recommendations_leave_year_id",
        "entitlement_recommendations",
        ["leave_year_id"],
    )

    op.create_table(
        "applied_entitlements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "leave_year_id",
            sa.Integer(),
            sa.ForeignKey("leave_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recommendation_id",
            sa.Integer(),
            sa.ForeignKey(
                "entitlement_recommendations.id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("dcc_hours", sa.Numeric(12, 6), nullable=False),
        sa.Column("spa_hours", sa.Numeric(12, 6), nullable=False),
        sa.Column("other_hours", sa.Numeric(12, 6), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "leave_year_id",
            name="uq_applied_entitlement_leave_year",
        ),
        sa.CheckConstraint(
            """
            mode IN (
                'calculated',
                'calculated_with_override',
                'manual'
            )
            """,
            name="ck_applied_entitlement_mode",
        ),
        sa.CheckConstraint(
            "dcc_hours >= 0",
            name="ck_applied_entitlement_dcc_hours",
        ),
        sa.CheckConstraint(
            "spa_hours >= 0",
            name="ck_applied_entitlement_spa_hours",
        ),
        sa.CheckConstraint(
            "other_hours >= 0",
            name="ck_applied_entitlement_other_hours",
        ),
    )

    op.create_index(
        "ix_applied_entitlements_leave_year_id",
        "applied_entitlements",
        ["leave_year_id"],
    )


def downgrade() -> None:
    """Remove annual-entitlement storage."""

    op.drop_index(
        "ix_applied_entitlements_leave_year_id",
        table_name="applied_entitlements",
    )
    op.drop_table("applied_entitlements")

    op.drop_index(
        "ix_entitlement_recommendations_leave_year_id",
        table_name="entitlement_recommendations",
    )
    op.drop_table("entitlement_recommendations")
