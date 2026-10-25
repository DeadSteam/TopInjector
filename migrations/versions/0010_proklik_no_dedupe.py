"""uq_queue_tasks_pending_click_url: don't dedupe manual proklik tasks

Revision ID: 0010_proklik_no_dedupe
Revises: 0009_geo_city_center_boolean
Create Date: 2026-10-21 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0010_proklik_no_dedupe'
down_revision: str | None = '0009_geo_city_center_boolean'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "uq_queue_tasks_pending_click_url"


def _create(where: str) -> None:
    op.create_index(
        _INDEX,
        "queue_tasks",
        ["project_id", "click_url"],
        unique=True,
        postgresql_where=sa.text(where),
        sqlite_where=sa.text(where),
    )


def upgrade() -> None:
    op.drop_index(_INDEX, table_name="queue_tasks")
    _create("status = 'pending' AND source != 'proklik'")


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="queue_tasks")
    _create("status = 'pending'")
