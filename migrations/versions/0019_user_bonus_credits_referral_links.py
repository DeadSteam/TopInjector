"""add bonus_credits to users and referral_links table

Revision ID: 0019_user_bonus_credits_referral_links
Revises: 0018_user_prepay
Create Date: 2026-10-28 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0019_user_bonus_credits_referral_links'
down_revision: str | None = '0018_user_prepay'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add bonus_credits column to users
    op.add_column(
        "users",
        sa.Column(
            "bonus_credits",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # Create referral_links table
    op.create_table(
        "referral_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("signups", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("code", name="uq_referral_link_code"),
    )
    op.create_index("ix_referral_links_code", "referral_links", ["code"])
    op.create_index("ix_referral_links_user_id", "referral_links", ["user_id"])


def downgrade() -> None:
    op.drop_table("referral_links")
    op.drop_column("users", "bonus_credits")
