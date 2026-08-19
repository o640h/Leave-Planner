"""Create the private workspace ownership boundary.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=30), nullable=False, server_default="admin"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("role = 'admin'", name="ck_workspace_membership_role"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership"),
    )
    op.create_index(
        "ix_workspace_memberships_workspace_id", "workspace_memberships", ["workspace_id"]
    )
    op.create_index("ix_workspace_memberships_user_id", "workspace_memberships", ["user_id"])

    connection = op.get_bind()
    workspace_table = sa.table(
        "workspaces",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String()),
    )
    connection.execute(workspace_table.insert().values(name="Leave Planner"))
    workspace_id = connection.scalar(
        sa.select(workspace_table.c.id).where(workspace_table.c.name == "Leave Planner")
    )
    if workspace_id is None:
        raise RuntimeError("The initial workspace could not be created")
    connection.execute(
        sa.text(
            "INSERT INTO workspace_memberships (workspace_id, user_id, role) "
            "SELECT :workspace_id, id, 'admin' FROM users"
        ),
        {"workspace_id": workspace_id},
    )

    with op.batch_alter_table("consultants") as batch:
        batch.add_column(sa.Column("workspace_id", sa.Integer(), nullable=True))
    connection.execute(
        sa.text("UPDATE consultants SET workspace_id = :workspace_id"),
        {"workspace_id": workspace_id},
    )
    with op.batch_alter_table("consultants") as batch:
        batch.alter_column("workspace_id", nullable=False)
        batch.create_foreign_key(
            "fk_consultants_workspace_id",
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index("ix_consultants_workspace_id", ["workspace_id"])

    with op.batch_alter_table("holiday_corrections") as batch:
        batch.add_column(sa.Column("workspace_id", sa.Integer(), nullable=True))
    connection.execute(
        sa.text("UPDATE holiday_corrections SET workspace_id = :workspace_id"),
        {"workspace_id": workspace_id},
    )
    with op.batch_alter_table("holiday_corrections") as batch:
        batch.alter_column("workspace_id", nullable=False)
        batch.create_foreign_key(
            "fk_holiday_corrections_workspace_id",
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index("ix_holiday_corrections_workspace_id", ["workspace_id"])

    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("workspace_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("actor_user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("actor_label", sa.String(length=100), nullable=True))
    connection.execute(
        sa.text(
            "UPDATE audit_events SET workspace_id = :workspace_id, actor_label = 'System Import'"
        ),
        {"workspace_id": workspace_id},
    )
    with op.batch_alter_table("audit_events") as batch:
        batch.alter_column("workspace_id", nullable=False)
        batch.alter_column("actor_label", nullable=False)
        batch.create_foreign_key(
            "fk_audit_events_workspace_id",
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_audit_events_actor_user_id",
            "users",
            ["actor_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_audit_events_workspace_id", ["workspace_id"])
        batch.create_index("ix_audit_events_actor_user_id", ["actor_user_id"])


def downgrade() -> None:
    with op.batch_alter_table("audit_events") as batch:
        batch.drop_index("ix_audit_events_actor_user_id")
        batch.drop_index("ix_audit_events_workspace_id")
        batch.drop_constraint("fk_audit_events_actor_user_id", type_="foreignkey")
        batch.drop_constraint("fk_audit_events_workspace_id", type_="foreignkey")
        batch.drop_column("actor_label")
        batch.drop_column("actor_user_id")
        batch.drop_column("workspace_id")
    with op.batch_alter_table("holiday_corrections") as batch:
        batch.drop_index("ix_holiday_corrections_workspace_id")
        batch.drop_constraint("fk_holiday_corrections_workspace_id", type_="foreignkey")
        batch.drop_column("workspace_id")
    with op.batch_alter_table("consultants") as batch:
        batch.drop_index("ix_consultants_workspace_id")
        batch.drop_constraint("fk_consultants_workspace_id", type_="foreignkey")
        batch.drop_column("workspace_id")
    op.drop_index("ix_workspace_memberships_user_id", table_name="workspace_memberships")
    op.drop_index("ix_workspace_memberships_workspace_id", table_name="workspace_memberships")
    op.drop_table("workspace_memberships")
    op.drop_table("workspaces")
