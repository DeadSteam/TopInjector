"""add_user_settings_columns

Revision ID: 0008_add_user_settings_columns
Revises: 0007_add_warmup_campaigns
Create Date: 2026-10-21 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0008_add_user_settings_columns'
down_revision: str | None = '0007_add_warmup_campaigns'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("messenger_settings", _JSON, nullable=True))
        batch.add_column(sa.Column("external_services", _JSON, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("external_services")
        batch.drop_column("messenger_settings")
