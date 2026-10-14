"""add_balance_tables

Revision ID: 0004_add_balance_tables
Revises: 0003_add_missing_columns
Create Date: 2026-10-13 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0004_add_balance_tables'
down_revision: str | None = '0003_add_missing_columns'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add balance_credits column to projects (stored as integer kopeks)
    op.add_column(
        "projects",
        sa.Column("balance_credits", sa.Integer(), nullable=False, server_default="0"),
    )

    # Create balance_transactions table
    op.create_table(
        "balance_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("type", sa.String(length=20), nullable=False, server_default="add"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_balance_transactions_project_id", "balance_transactions", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_balance_transactions_project_id", table_name="balance_transactions")
    op.drop_table("balance_transactions")
    op.drop_column("projects", "balance_credits")
