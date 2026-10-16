"""add_warmup_campaigns_table

Revision ID: 0007_add_warmup_campaigns
Revises: 0006_add_geo_code_presets
Create Date: 2026-10-16 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0007_add_warmup_campaigns'
down_revision: str | None = '0006_add_geo_code_presets'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "warmup_campaigns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("project_name", sa.String(200), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("clicks_per_hour", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("total_target", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("completed_clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_warmup_campaign_user_name"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_warmup_campaigns_user_id"), "warmup_campaigns", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_warmup_campaigns_user_id"), table_name="warmup_campaigns")
    op.drop_table("warmup_campaigns")
