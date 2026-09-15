"""Create workspace roles, active selection, and PostgreSQL isolation.

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WORKSPACE_ROOTS = ("consultants", "holiday_corrections", "audit_events")


def _create_postgresql_isolation() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    # The application login already exists on deployed PostgreSQL installations. Grants are
    # repeated explicitly because existing objects pre-date the default-privilege rule.
    application_role_exists = connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM pg_roles "
            "WHERE rolname = 'leave_planner_application')"
        )
    )
    if application_role_exists:
        connection.execute(sa.text("GRANT USAGE ON SCHEMA public TO leave_planner_application"))
        connection.execute(
            sa.text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
                "TO leave_planner_application"
            )
        )
        connection.execute(
            sa.text(
                "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public "
                "TO leave_planner_application"
            )
        )

    for table in ("workspaces", "workspace_memberships", *_WORKSPACE_ROOTS):
        connection.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))

    current_user = (
        "NULLIF(current_setting('leave_planner.user_id', true), '')::integer"
    )
    current_workspace = (
        "NULLIF(current_setting('leave_planner.workspace_id', true), '')::integer"
    )
    connection.execute(
        sa.text(
            "CREATE POLICY workspace_memberships_select ON workspace_memberships FOR SELECT "
            f"USING (user_id = {current_user} OR workspace_id = {current_workspace})"
        )
    )
    connection.execute(
        sa.text(
            "CREATE POLICY workspace_memberships_write ON workspace_memberships "
            "FOR ALL USING "
            f"(workspace_id = {current_workspace}) WITH CHECK "
            f"(workspace_id = {current_workspace})"
        )
    )
    connection.execute(
        sa.text(
            "CREATE POLICY workspaces_select ON workspaces FOR SELECT USING ("
            f"id = {current_workspace} OR EXISTS ("
            "SELECT 1 FROM workspace_memberships membership "
            "WHERE membership.workspace_id = workspaces.id "
            f"AND membership.user_id = {current_user}))"
        )
    )
    connection.execute(
        sa.text(
            "CREATE POLICY workspaces_write ON workspaces FOR ALL USING "
            f"(id = {current_workspace}) WITH CHECK (id = {current_workspace})"
        )
    )
    for table in _WORKSPACE_ROOTS:
        connection.execute(
            sa.text(
                f"CREATE POLICY {table}_workspace ON {table} FOR ALL USING "
                f"(workspace_id = {current_workspace}) WITH CHECK "
                f"(workspace_id = {current_workspace})"
            )
        )


def upgrade() -> None:
    with op.batch_alter_table("consultants") as batch:
        batch.create_unique_constraint(
            "uq_consultants_workspace_id_id", ("workspace_id", "id")
        )

    with op.batch_alter_table("workspace_memberships") as batch:
        batch.drop_constraint("ck_workspace_membership_role", type_="check")
        batch.add_column(sa.Column("linked_consultant_id", sa.Integer(), nullable=True))
        batch.create_check_constraint(
            "ck_workspace_membership_role", "role IN ('owner', 'admin', 'member')"
        )
        batch.create_check_constraint(
            "ck_workspace_membership_consultant_role",
            "role = 'member' OR linked_consultant_id IS NULL",
        )
        batch.create_foreign_key(
            "fk_workspace_membership_linked_consultant",
            "consultants",
            ["workspace_id", "linked_consultant_id"],
            ["workspace_id", "id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            "ix_workspace_memberships_linked_consultant_id", ["linked_consultant_id"]
        )

    op.create_index(
        "uq_workspace_memberships_single_owner",
        "workspace_memberships",
        ("workspace_id",),
        unique=True,
        postgresql_where=sa.text("role = 'owner'"),
        sqlite_where=sa.text("role = 'owner'"),
    )

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("last_workspace_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_users_last_workspace_id",
            "workspaces",
            ["last_workspace_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_users_last_workspace_id", ["last_workspace_id"])

    with op.batch_alter_table("user_sessions") as batch:
        batch.add_column(sa.Column("active_workspace_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_user_sessions_active_workspace_id",
            "workspaces",
            ["active_workspace_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_user_sessions_active_workspace_id", ["active_workspace_id"])

    _create_postgresql_isolation()


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        policies = {
            "workspaces": ("workspaces_select", "workspaces_write"),
            "workspace_memberships": (
                "workspace_memberships_select",
                "workspace_memberships_write",
            ),
            **{table: (f"{table}_workspace",) for table in _WORKSPACE_ROOTS},
        }
        for table, names in policies.items():
            for name in names:
                connection.execute(sa.text(f"DROP POLICY {name} ON {table}"))
            connection.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

    with op.batch_alter_table("user_sessions") as batch:
        batch.drop_index("ix_user_sessions_active_workspace_id")
        batch.drop_constraint("fk_user_sessions_active_workspace_id", type_="foreignkey")
        batch.drop_column("active_workspace_id")
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_last_workspace_id")
        batch.drop_constraint("fk_users_last_workspace_id", type_="foreignkey")
        batch.drop_column("last_workspace_id")
    op.drop_index(
        "uq_workspace_memberships_single_owner", table_name="workspace_memberships"
    )
    with op.batch_alter_table("workspace_memberships") as batch:
        batch.drop_index("ix_workspace_memberships_linked_consultant_id")
        batch.drop_constraint(
            "fk_workspace_membership_linked_consultant", type_="foreignkey"
        )
        batch.drop_constraint("ck_workspace_membership_consultant_role", type_="check")
        batch.drop_constraint("ck_workspace_membership_role", type_="check")
        batch.create_check_constraint("ck_workspace_membership_role", "role = 'admin'")
        batch.drop_column("linked_consultant_id")
    with op.batch_alter_table("consultants") as batch:
        batch.drop_constraint("uq_consultants_workspace_id_id", type_="unique")
