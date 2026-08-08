"""Create consultants table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the central consultant directory."""

    op.create_table(
        "consultants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("post_title", sa.String(length=200), nullable=True),
    )

    op.create_index(
        "ix_consultants_name",
        "consultants",
        ["name"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the consultant directory when rolling back."""

    op.drop_index("ix_consultants_name", table_name="consultants")
    op.drop_table("consultants")
