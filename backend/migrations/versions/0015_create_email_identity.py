"""Replace the disposable shared account with email identity fields.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BUSINESS_TABLES = ("consultants", "holiday_corrections", "audit_events")


def upgrade() -> None:
    connection = op.get_bind()
    occupied = {
        table: int(connection.scalar(sa.text(f"SELECT COUNT(*) FROM {table}")) or 0)
        for table in _BUSINESS_TABLES
    }
    occupied = {table: count for table, count in occupied.items() if count}
    if occupied:
        detail = ", ".join(f"{table}={count}" for table, count in sorted(occupied.items()))
        raise RuntimeError(
            "Email identity requires the approved clean start; "
            f"legacy business data remains ({detail})"
        )

    # The operator explicitly approved discarding the practically empty shared Admin boundary.
    connection.execute(sa.text("DELETE FROM workspace_memberships"))
    connection.execute(sa.text("DELETE FROM user_sessions"))
    connection.execute(sa.text("DELETE FROM security_events"))
    connection.execute(sa.text("DELETE FROM users"))

    with op.batch_alter_table("users", recreate="always") as batch:
        batch.drop_constraint("uq_users_display_name", type_="unique")
        batch.drop_column("enabled")
        batch.add_column(sa.Column("public_id", sa.String(length=32), nullable=False))
        batch.add_column(sa.Column("canonical_email", sa.String(length=320), nullable=False))
        batch.add_column(sa.Column("display_email", sa.String(length=320), nullable=False))
        batch.add_column(sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column(
                "security_state",
                sa.String(length=30),
                nullable=False,
                server_default="pending_verification",
            )
        )
        batch.create_unique_constraint("uq_users_public_id", ["public_id"])
        batch.create_unique_constraint("uq_users_canonical_email", ["canonical_email"])
        batch.create_check_constraint(
            "ck_users_security_state",
            "security_state IN ('pending_verification', 'active', 'disabled', 'deleted')",
        )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT COUNT(*) FROM users")):
        raise RuntimeError("Email accounts must be removed before downgrading revision 0015")

    with op.batch_alter_table("users", recreate="always") as batch:
        batch.drop_constraint("ck_users_security_state", type_="check")
        batch.drop_constraint("uq_users_canonical_email", type_="unique")
        batch.drop_constraint("uq_users_public_id", type_="unique")
        batch.drop_column("security_state")
        batch.drop_column("email_verified_at")
        batch.drop_column("display_email")
        batch.drop_column("canonical_email")
        batch.drop_column("public_id")
        batch.add_column(
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch.create_unique_constraint("uq_users_display_name", ["display_name"])
