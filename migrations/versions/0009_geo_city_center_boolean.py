"""geo_code_presets.is_city_center: text -> boolean

Revision ID: 0009_geo_city_center_boolean
Revises: 0008_add_user_settings_columns
Create Date: 2026-10-21 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0009_geo_city_center_boolean'
down_revision: str | None = '0008_add_user_settings_columns'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("geo_code_presets") as batch:
        batch.alter_column(
            "is_city_center",
            existing_type=sa.Text(),
            type_=sa.Boolean(),
            existing_nullable=True,
            postgresql_using="is_city_center::boolean",
        )


def downgrade() -> None:
    with op.batch_alter_table("geo_code_presets") as batch:
        batch.alter_column(
            "is_city_center",
            existing_type=sa.Boolean(),
            type_=sa.Text(),
            existing_nullable=True,
            postgresql_using="is_city_center::text",
        )
