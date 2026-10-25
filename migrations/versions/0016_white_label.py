"""white-label branding settings per user

Revision ID: 0016_white_label
Revises: 0015_seed_plans
Create Date: 2026-10-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0016_white_label'
down_revision: str | None = '0015_seed_plans'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "white_labels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("dns_status", sa.String(length=20), nullable=False),
        sa.Column("platform_name", sa.String(length=200), nullable=False),
        sa.Column("accent_color", sa.String(length=20), nullable=False),
        sa.Column("description_md", sa.Text(), nullable=False),
        sa.Column("welcome_text_md", sa.Text(), nullable=False),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("logo_light_key", sa.String(length=500), nullable=True),
        sa.Column("logo_dark_key", sa.String(length=500), nullable=True),
        sa.Column("favicon_key", sa.String(length=500), nullable=True),
        sa.Column("banner_catalog_key", sa.String(length=500), nullable=True),
        sa.Column("banner_homepage_key", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_white_labels_user_id", "user_id", unique=True),
    )


def downgrade() -> None:
    op.drop_table("white_labels")
