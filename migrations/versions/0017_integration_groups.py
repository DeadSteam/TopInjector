"""integration groups and servers for project assignment

Add integration_groups and integration_servers tables, plus
integration_group_id column on projects.

Revision ID: 0017_integration_groups
Revises: 0016_white_label
Create Date: 2026-10-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0017_integration_groups'
down_revision: str | None = '0016_white_label'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- integration_groups --------------------------------------------------
    op.create_table(
        "integration_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("max_projects", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("current_project_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rpm_limit", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("ip_whitelist", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("use_reserved", sa.Boolean(), nullable=False, server_default="f"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="f"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="t"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_integration_groups_user_id", "user_id"),
    )

    # --- integration_servers -------------------------------------------------
    op.create_table(
        "integration_servers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), sa.ForeignKey("integration_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("ip_address", sa.String(length=45)),
        sa.Column("software_type", sa.String(length=30), nullable=False, server_default="portal"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="t"),
        sa.Column("max_queries_per_minute", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("notes", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_integration_servers_group_id", "group_id"),
    )

    # --- projects.integration_group_id ---------------------------------------
    op.add_column(
        "projects",
        sa.Column("integration_group_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_projects_integration_group_id",
        "projects",
        "integration_groups",
        ["integration_group_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_projects_integration_group_id", "projects", type_="foreignkey")
    op.drop_column("projects", "integration_group_id")
    op.drop_table("integration_servers")
    op.drop_table("integration_groups")
