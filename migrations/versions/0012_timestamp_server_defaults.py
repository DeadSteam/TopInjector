"""warmup_campaigns, geo_code_presets: server defaults for created_at/updated_at

Both tables were created without them, so every insert that relied on the model's
server_default failed on Postgres (e.g. creating a warmup campaign).

Revision ID: 0012_timestamp_server_defaults
Revises: 0011_drop_project_domain_uq
Create Date: 2026-10-21 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0012_timestamp_server_defaults'
down_revision: str | None = '0011_drop_project_domain_uq'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("warmup_campaigns", "geo_code_presets")
_COLUMNS = ("created_at", "updated_at")


def upgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch:
            for column in _COLUMNS:
                batch.alter_column(
                    column,
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    server_default=sa.func.now(),
                )


def downgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch:
            for column in _COLUMNS:
                batch.alter_column(
                    column,
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    server_default=None,
                )
