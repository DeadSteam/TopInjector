"""add prepay_per_click_cop to users table

Revision ID: 0018_user_prepay
Revises: 0017_integration_groups
Create Date: 2026-10-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0018_user_prepay'
down_revision: str | None = '0017_integration_groups'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "prepay_per_click_cop",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "prepay_per_click_cop")
