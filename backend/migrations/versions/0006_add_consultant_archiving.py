"""Add consultant archiving.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow consultant records to be hidden without losing history."""

    op.add_column(
        "consultants",
        sa.Column("archived_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_consultants_archived_at",
        "consultants",
        ["archived_at"],
    )


def downgrade() -> None:
    """Remove consultant archiving."""

    op.drop_index("ix_consultants_archived_at", table_name="consultants")
    op.drop_column("consultants", "archived_at")
