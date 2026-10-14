"""add_geo_code_presets_table

Revision ID: 0006_add_geo_code_presets
Revises: 0005_add_audit_log
Create Date: 2026-10-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0006_add_geo_code_presets'
down_revision: str | None = '0005_add_audit_log'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "geo_code_presets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("yandex_geo_id", sa.JSON(), nullable=True),
        sa.Column("country_code", sa.String(3), nullable=False, server_default="ru"),
        sa.Column("region_name", sa.String(200), nullable=False),
        sa.Column("city_name", sa.String(200), nullable=False),
        sa.Column("is_city_center", sa.JSON(), nullable=True),
        sa.Column("search_aliases", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_primary_key("pk_geo_code_presets_id", "geo_code_presets", ["id"])
    op.create_unique_index(
        "uq_geo_code_preset_city_region",
        "geo_code_presets",
        ["city_name", "region_name"]
    )
    op.create_index(
        "ix_geo_code_presets_city_name",
        "geo_code_presets",
        ["city_name"]
    )
    op.create_index(
        "ix_geo_code_presets_region_name",
        "geo_code_presets",
        ["region_name"]
    )


def downgrade() -> None:
    op.drop_table("geo_code_presets")
