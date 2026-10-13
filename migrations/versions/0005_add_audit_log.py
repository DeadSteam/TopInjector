"""add_project_audit_log_table

Revision ID: 0005_add_audit_log
Revises: 0004_add_balance_tables
Create Date: 2026-10-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0005_add_audit_log'
down_revision: str | None = '0004_add_balance_tables'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("old_values", sa.JSON(), nullable=True),
        sa.Column("new_values", sa.JSON(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("LENGTH(action) > 0", name="ck_project_audit_log_action_not_empty"),
    )
    op.create_primary_key("pk_project_audit_log_id", "project_audit_log", ["id"])
    op.create_index("ix_project_audit_log_project_id", "project_audit_log", ["project_id"])
    op.create_index("ix_project_audit_log_user_id", "project_audit_log", ["user_id"])
    op.create_index("ix_project_audit_log_actor_user_id", "project_audit_log", ["actor_user_id"])
    op.create_index("ix_project_audit_log_created_at", "project_audit_log", ["created_at"])
    op.create_foreign_key(
        "fk_project_audit_log_project_id_projects",
        "project_audit_log", "projects",
        ["project_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_project_audit_log_user_id_users",
        "project_audit_log", "users",
        ["user_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_project_audit_log_actor_user_id_users",
        "project_audit_log", "users",
        ["actor_user_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_table("project_audit_log")
