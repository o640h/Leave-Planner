"""Add reviewed cancellation requests to approved leave bookings.

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("leave_bookings") as batch:
        batch.add_column(sa.Column("cancellation_requested_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("cancellation_requested_by_user_id", sa.Integer()))
        batch.create_foreign_key(
            "fk_leave_booking_cancellation_request_user",
            "users",
            ["cancellation_requested_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_check_constraint(
            "ck_leave_booking_cancellation_request",
            "cancellation_requested_at IS NULL OR state = 'approved'",
        )
        batch.create_index(
            "ix_leave_booking_cancellation_requested_at",
            ["cancellation_requested_at"],
        )


def downgrade() -> None:
    with op.batch_alter_table("leave_bookings") as batch:
        batch.drop_index("ix_leave_booking_cancellation_requested_at")
        batch.drop_constraint("ck_leave_booking_cancellation_request", type_="check")
        batch.drop_constraint("fk_leave_booking_cancellation_request_user", type_="foreignkey")
        batch.drop_column("cancellation_requested_by_user_id")
        batch.drop_column("cancellation_requested_at")
