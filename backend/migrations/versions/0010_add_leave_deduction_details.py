"""Add source details to dated leave-deduction snapshots.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-17
"""

from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("leave_booking_days") as batch:
        batch.add_column(sa.Column("contracted_pas", sa.Numeric(9, 3), nullable=True))
        batch.add_column(sa.Column("deduction_factor", sa.String(length=64), nullable=True))

    connection = op.get_bind()
    rows = tuple(
        connection.execute(
            sa.text(
                """
            SELECT leave_booking_days.id, job_plan_versions.contracted_pas
            FROM leave_booking_days
            JOIN job_plan_versions
              ON job_plan_versions.id = leave_booking_days.job_plan_id
            """
            )
        ).mappings()
    )
    for row in rows:
        contracted_pas = Decimal(str(row["contracted_pas"]))
        factor = Decimal("10") / max(contracted_pas, Decimal("10"))
        connection.execute(
            sa.text(
                """
                UPDATE leave_booking_days
                SET contracted_pas = :contracted_pas,
                    deduction_factor = :deduction_factor
                WHERE id = :day_id
                """
            ),
            {
                "contracted_pas": format(contracted_pas, "f"),
                "deduction_factor": format(factor, "f"),
                "day_id": row["id"],
            },
        )


def downgrade() -> None:
    with op.batch_alter_table("leave_booking_days") as batch:
        batch.drop_column("deduction_factor")
        batch.drop_column("contracted_pas")
