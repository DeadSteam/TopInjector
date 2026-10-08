"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-08 15:44:50.874878
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
task_source = sa.Enum("strategy", "autoburst", "proklik", name="task_source")
task_status = sa.Enum("pending", "in_progress", "completed", "not_found", "stuck", name="task_status")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("region", sa.String(length=50), nullable=True),
        sa.Column("strategy_type", sa.String(length=20), nullable=False),
        sa.Column("daily_limit", sa.Integer(), nullable=False),
        sa.Column("geo_settings", JSONType, nullable=False),
        sa.Column("integrations", JSONType, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "domain", name="uq_projects_user_domain"),
    )
    op.create_index("ix_projects_domain", "projects", ["domain"], unique=False)
    op.create_index("ix_projects_user_id", "projects", ["user_id"], unique=False)

    op.create_table(
        "queries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("click_url", sa.Text(), nullable=True),
        sa.Column("geo", JSONType, nullable=False),
        sa.Column("daily_clicks", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("boost_min", sa.Integer(), nullable=True),
        sa.Column("boost_max", sa.Integer(), nullable=True),
        sa.Column("frequency", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_queries_project_id", "queries", ["project_id"], unique=False)

    op.create_table(
        "queue_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("query_id", sa.Uuid(), nullable=True),
        sa.Column("click_url", sa.Text(), nullable=False),
        sa.Column("source", task_source, nullable=False),
        sa.Column("status", task_status, nullable=False),
        sa.Column("geo", JSONType, nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("pending_check_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["query_id"], ["queries.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_queue_tasks_project_id", "queue_tasks", ["project_id"], unique=False)
    op.create_index("ix_queue_tasks_status", "queue_tasks", ["status"], unique=False)
    op.create_index(
        "uq_queue_tasks_pending_click_url",
        "queue_tasks",
        ["project_id", "click_url"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_table("queue_tasks")
    op.drop_table("queries")
    op.drop_table("projects")
    op.drop_table("users")
    # PostgreSQL keeps enum types after DROP TABLE; remove them so upgrade can run again.
    bind = op.get_bind()
    task_status.drop(bind, checkfirst=True)
    task_source.drop(bind, checkfirst=True)
