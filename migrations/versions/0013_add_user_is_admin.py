"""add user is_admin column for admin accounts with infinite project balance

Revision ID: 0013_add_user_is_admin
Revises: 0012_timestamp_server_defaults
Create Date: 2026-10-24 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0013_add_user_is_admin'
down_revision: str | None = '0012_timestamp_server_defaults'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false"),),
    )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_admin")
