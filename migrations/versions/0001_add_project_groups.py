"""add_project_groups

Revision ID: 0001_add_project_groups
Revises: 57d4586e4b32
Create Date: 2026-10-09 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0001_add_project_groups'
down_revision: str | None = '57d4586e4b32'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # project_groups table
    op.create_table(
        "project_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("icon", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_groups_user_id", "project_groups", ["user_id"], unique=False)

    # add group_id column to projects
    op.add_column(
        "projects",
        sa.Column("group_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_projects_group_id", "projects", "project_groups",
        ["group_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_projects_group_id", "projects", type_="foreignkey")
    op.drop_column("projects", "group_id")
    op.drop_index("ix_project_groups_user_id", table_name="project_groups")
    op.drop_table("project_groups")
