"""Create workspace invitations, people history, transfers, and lifecycle state.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_postgresql_isolation() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    application_role_exists = connection.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leave_planner_application')")
    )
    tables = (
        "workspace_invitations",
        "workspace_ownership_transfers",
        "workspace_events",
    )
    if application_role_exists:
        connection.execute(
            sa.text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON "
                + ", ".join(tables)
                + " TO leave_planner_application"
            )
        )
        connection.execute(
            sa.text(
                "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public "
                "TO leave_planner_application"
            )
        )

    current_workspace = "NULLIF(current_setting('leave_planner.workspace_id', true), '')::integer"
    for table in tables:
        connection.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        connection.execute(
            sa.text(
                f"CREATE POLICY {table}_workspace ON {table} FOR ALL USING "
                f"(workspace_id = {current_workspace}) WITH CHECK "
                f"(workspace_id = {current_workspace})"
            )
        )


def upgrade() -> None:
    with op.batch_alter_table("workspaces") as batch:
        batch.add_column(
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active")
        )
        batch.add_column(sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("purge_after", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint("ck_workspaces_status", "status IN ('active', 'closed')")
        batch.create_check_constraint(
            "ck_workspaces_lifecycle",
            "(status = 'active' AND closed_at IS NULL AND purge_after IS NULL) OR "
            "(status = 'closed' AND closed_at IS NOT NULL AND purge_after IS NOT NULL)",
        )

    op.create_table(
        "workspace_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("canonical_email", sa.String(length=320), nullable=False),
        sa.Column("display_email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("linked_consultant_id", sa.Integer(), nullable=True),
        sa.Column(
            "invited_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "claimed_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "action_token_id",
            sa.Integer(),
            sa.ForeignKey("account_action_tokens.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('admin', 'member')", name="ck_workspace_invitation_role"),
        sa.CheckConstraint(
            "role = 'member' OR linked_consultant_id IS NULL",
            name="ck_workspace_invitation_consultant_role",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'revoked')",
            name="ck_workspace_invitation_status",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "linked_consultant_id"],
            ["consultants.workspace_id", "consultants.id"],
            name="fk_workspace_invitation_linked_consultant",
            ondelete="RESTRICT",
        ),
    )
    for column in (
        "workspace_id",
        "linked_consultant_id",
        "invited_by_user_id",
        "claimed_by_user_id",
        "action_token_id",
        "expires_at",
    ):
        op.create_index(f"ix_workspace_invitations_{column}", "workspace_invitations", [column])
    op.create_index(
        "uq_workspace_invitations_pending_email",
        "workspace_invitations",
        ["workspace_id", "canonical_email"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "workspace_ownership_transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'cancelled')",
            name="ck_workspace_ownership_transfer_status",
        ),
    )
    for column in ("workspace_id", "from_user_id", "to_user_id", "expires_at"):
        op.create_index(
            f"ix_workspace_ownership_transfers_{column}",
            "workspace_ownership_transfers",
            [column],
        )
    op.create_index(
        "uq_workspace_ownership_transfers_pending",
        "workspace_ownership_transfers",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "workspace_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_label", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    )
    op.create_index("ix_workspace_events_workspace_id", "workspace_events", ["workspace_id"])
    op.create_index("ix_workspace_events_actor_user_id", "workspace_events", ["actor_user_id"])
    op.create_index("ix_workspace_events_event_type", "workspace_events", ["event_type"])
    op.create_index("ix_workspace_events_recorded_at", "workspace_events", ["recorded_at"])
    op.create_index(
        "ix_workspace_events_workspace_recorded",
        "workspace_events",
        ["workspace_id", "recorded_at"],
    )

    _enable_postgresql_isolation()


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        for table in (
            "workspace_events",
            "workspace_ownership_transfers",
            "workspace_invitations",
        ):
            connection.execute(sa.text(f"DROP POLICY {table}_workspace ON {table}"))
            connection.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

    op.drop_table("workspace_events")
    op.drop_table("workspace_ownership_transfers")
    op.drop_table("workspace_invitations")
    with op.batch_alter_table("workspaces") as batch:
        batch.drop_constraint("ck_workspaces_lifecycle", type_="check")
        batch.drop_constraint("ck_workspaces_status", type_="check")
        batch.drop_column("purge_after")
        batch.drop_column("closed_at")
        batch.drop_column("status")
