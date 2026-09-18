"""Simplify leave bookings to requested, approved, and cancelled.

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("leave_bookings") as batch:
        batch.drop_constraint("ck_leave_booking_state", type_="check")

    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE leave_bookings SET state = 'requested' WHERE state = 'planned'")
    )
    connection.execute(
        sa.text("UPDATE leave_bookings SET state = 'approved' WHERE state = 'taken'")
    )

    with op.batch_alter_table("leave_bookings") as batch:
        batch.create_check_constraint(
            "ck_leave_booking_state",
            "state IN ('requested', 'approved', 'cancelled')",
        )


def downgrade() -> None:
    with op.batch_alter_table("leave_bookings") as batch:
        batch.drop_constraint("ck_leave_booking_state", type_="check")

    op.execute("UPDATE leave_bookings SET state = 'planned' WHERE state = 'requested'")

    with op.batch_alter_table("leave_bookings") as batch:
        batch.create_check_constraint(
            "ck_leave_booking_state",
            "state IN ('planned', 'approved', 'taken', 'cancelled')",
        )
