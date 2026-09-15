"""Create single-use account actions and email delivery records.

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_action_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("canonical_email", sa.String(length=320), nullable=False),
        sa.Column("display_email", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "purpose IN ('email_verification', 'password_reset', 'invitation', 'email_change')",
            name="ck_account_action_token_purpose",
        ),
        sa.CheckConstraint(
            "purpose = 'invitation' OR user_id IS NOT NULL",
            name="ck_account_action_token_user",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_account_action_token_expiry",
        ),
        sa.UniqueConstraint("token_hash", name="uq_account_action_tokens_hash"),
    )
    op.create_index("ix_account_action_tokens_user_id", "account_action_tokens", ["user_id"])
    op.create_index(
        "ix_account_action_tokens_workspace_id", "account_action_tokens", ["workspace_id"]
    )
    op.create_index("ix_account_action_tokens_expires_at", "account_action_tokens", ["expires_at"])

    op.create_table(
        "email_delivery_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "action_token_id",
            sa.Integer(),
            sa.ForeignKey("account_action_tokens.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("recipient_hint", sa.String(length=340), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider_message_id", sa.String(length=100), nullable=True),
        sa.Column("failure_code", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed')",
            name="ck_email_delivery_attempt_status",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_email_delivery_attempt_idempotency"),
    )
    op.create_index(
        "ix_email_delivery_attempts_action_token_id",
        "email_delivery_attempts",
        ["action_token_id"],
    )
    op.create_index(
        "ix_email_delivery_attempts_created_at", "email_delivery_attempts", ["created_at"]
    )

    with op.batch_alter_table("user_sessions") as batch:
        batch.add_column(sa.Column("reauthenticated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("user_sessions") as batch:
        batch.drop_column("reauthenticated_at")
    op.drop_index("ix_email_delivery_attempts_created_at", table_name="email_delivery_attempts")
    op.drop_index(
        "ix_email_delivery_attempts_action_token_id", table_name="email_delivery_attempts"
    )
    op.drop_table("email_delivery_attempts")
    op.drop_index("ix_account_action_tokens_expires_at", table_name="account_action_tokens")
    op.drop_index("ix_account_action_tokens_workspace_id", table_name="account_action_tokens")
    op.drop_index("ix_account_action_tokens_user_id", table_name="account_action_tokens")
    op.drop_table("account_action_tokens")
