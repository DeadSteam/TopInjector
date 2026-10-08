"""add_project_tokens

Revision ID: 2509706337a6
Revises: 0001
Create Date: 2026-10-08 16:42:13.312649
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

JSONType = sa.JSON().with_variant(sa.dialects.postgresql.JSONB(astext_type=sa.Text()), "postgresql")

revision: str = '2509706337a6'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "project_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("token_string", sa.String(length=64), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "project_id", name="uq_user_project_token"),
    )
    op.create_index("ix_project_tokens_user_id", "project_tokens", ["user_id"], unique=False)
    op.create_index("ix_project_tokens_token_string", "project_tokens", ["token_string"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_project_tokens_token_string", table_name="project_tokens")
    op.drop_index("ix_project_tokens_user_id", table_name="project_tokens")
    op.drop_table("project_tokens")
