"""Remove unused public-holiday worked date.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("public_holiday_treatments") as batch:
        batch.drop_column("worked_date")


def downgrade() -> None:
    with op.batch_alter_table("public_holiday_treatments") as batch:
        batch.add_column(sa.Column("worked_date", sa.Date(), nullable=True))
