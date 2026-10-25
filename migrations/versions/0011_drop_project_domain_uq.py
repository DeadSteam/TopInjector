"""projects: allow several projects with the same domain per user (project copy)

Revision ID: 0011_drop_project_domain_uq
Revises: 0010_proklik_no_dedupe
Create Date: 2026-10-21 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = '0011_drop_project_domain_uq'
down_revision: str | None = '0010_proklik_no_dedupe'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("uq_projects_user_domain", type_="unique")


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.create_unique_constraint("uq_projects_user_domain", ["user_id", "domain"])
