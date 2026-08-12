"""Remove unused flexible job-plan hours.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_plan_versions") as batch:
        batch.drop_column("additional_dcc_hours")
        batch.drop_column("additional_spa_hours")


def downgrade() -> None:
    with op.batch_alter_table("job_plan_versions") as batch:
        batch.add_column(
            sa.Column(
                "additional_dcc_hours",
                sa.Numeric(9, 3),
                nullable=False,
                server_default="0",
            )
        )
        batch.add_column(
            sa.Column(
                "additional_spa_hours",
                sa.Numeric(9, 3),
                nullable=False,
                server_default="0",
            )
        )
