"""change projects.balance_credits from INTEGER to BIGINT to support _ADMIN_BALANCE (2**63-1).

Revision ID: 0020_bigint_balance_credits
Revises: 0019_user_bonus_credits_referral_links
Create Date: 2026-10-29 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0020_bigint_balance_credits'
down_revision: str | None = '0019_user_bonus_credits_referral_links'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "projects",
        "balance_credits",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_server_default=sa.text("0"),
    )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.alter_column(
            "balance_credits",
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_server_default=sa.text("0"),
        )
