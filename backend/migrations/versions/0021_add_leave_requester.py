"""Record the Member who submitted a leave request.

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("leave_bookings") as batch:
        batch.add_column(sa.Column("requested_by_user_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_leave_booking_request_user",
            "users",
            ["requested_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "ix_leave_bookings_requested_by_user_id",
            ["requested_by_user_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("leave_bookings") as batch:
        batch.drop_index("ix_leave_bookings_requested_by_user_id")
        batch.drop_constraint("fk_leave_booking_request_user", type_="foreignkey")
        batch.drop_column("requested_by_user_id")
