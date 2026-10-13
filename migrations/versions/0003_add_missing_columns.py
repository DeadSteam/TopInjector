"""0003_add_missing_columns

Revision ID: 0003_add_missing_columns
Revises: 0002_add_project_delegates
Create Date: 2026-10-12 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0003_add_missing_columns'
down_revision: str | None = '0002_add_project_delegates'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Projects: scheduling_window (store schedule start/end times)
    op.add_column("projects", sa.Column("scheduling_window", sa.JSON(), nullable=True))

    # Projects: query_modifications (flags: capital_first, random_caps, typos, trailing_space)
    op.add_column(
        "projects",
        sa.Column("query_modifications", sa.JSON(), nullable=False, server_default="{}"),
    )

    # Projects: auto_stop_at (automatic project stop date/time)
    op.add_column("projects", sa.Column("auto_stop_at", sa.DateTime(timezone=True), nullable=True))

    # Queries: query_modifications (per-query flags)
    op.add_column(
        "queries",
        sa.Column("query_modifications", sa.JSON(), nullable=False, server_default="{}"),
    )

    # Users: avatar_url (profile photo URL)
    op.add_column("users", sa.Column("avatar_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
    op.drop_column("queries", "query_modifications")
    op.drop_column("projects", "auto_stop_at")
    op.drop_column("projects", "query_modifications")
    op.drop_column("projects", "scheduling_window")
