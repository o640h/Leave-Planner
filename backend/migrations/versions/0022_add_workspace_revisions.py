"""Add workspace aggregate revisions for optimistic concurrency.

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("workspaces") as batch:
        batch.add_column(
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1")
        )
        batch.create_check_constraint("ck_workspaces_revision", "revision >= 1")


def downgrade() -> None:
    with op.batch_alter_table("workspaces") as batch:
        batch.drop_constraint("ck_workspaces_revision", type_="check")
        batch.drop_column("revision")
