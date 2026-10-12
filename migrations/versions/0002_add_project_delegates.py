"""add_project_delegates

Revision ID: 0002_add_project_delegates
Revises: 0001_add_project_groups
Create Date: 2026-10-09 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0002_add_project_delegates'
down_revision: str | None = '0001_add_project_groups'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_delegates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("delegate_user_id", sa.Uuid(), nullable=False),
        sa.Column("inviter_user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="view"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delegate_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inviter_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "delegate_user_id", name="uq_project_delegate"),
    )
    op.create_index("ix_project_delegates_project_id", "project_delegates", ["project_id"], unique=False)
    op.create_index("ix_project_delegates_delegate_user_id", "project_delegates", ["delegate_user_id"], unique=False)
    op.create_index("ix_project_delegates_inviter_user_id", "project_delegates", ["inviter_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_project_delegates_inviter_user_id", table_name="project_delegates")
    op.drop_index("ix_project_delegates_delegate_user_id", table_name="project_delegates")
    op.drop_index("ix_project_delegates_project_id", table_name="project_delegates")
    with op.batch_alter_table("project_delegates", schema=None) as batch_op:
        op.drop_table("project_delegates")
