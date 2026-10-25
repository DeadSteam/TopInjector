"""seed subscription plans and put existing users on the Start plan

Revision ID: 0015_seed_plans
Revises: 0014_platform_models
Create Date: 2026-10-25 00:00:00.000000
"""

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import context, op

revision: str = '0015_seed_plans'
down_revision: str | None = '0014_platform_models'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# slug, display_name, price_per_day (kop), price_per_month (kop), max_users, max_projects
_PLANS = [
    ("start", "Start", 0, 0, 5, 1),
    ("lite", "Lite", 10000, 300000, 20, 10),
    ("plus", "Plus", 16000, 480000, 50, 25),
    ("pro", "Pro", 33000, 990000, 100, 75),
    ("ultra", "Ultra", 50000, 1500000, 200, 150),
    ("max", "Max", 85000, 2550000, 500, 500),
]

_plans_t = sa.table(
    "plans",
    sa.column("id", sa.Uuid()),
    sa.column("slug", sa.String()),
    sa.column("display_name", sa.String()),
    sa.column("is_active", sa.Boolean()),
    sa.column("price_per_day", sa.Integer()),
    sa.column("price_per_month", sa.Integer()),
    sa.column("max_users", sa.Integer()),
    sa.column("max_projects", sa.Integer()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

_user_plans_t = sa.table(
    "user_plans",
    sa.column("id", sa.Uuid()),
    sa.column("user_id", sa.Uuid()),
    sa.column("plan_id", sa.Uuid()),
    sa.column("is_active", sa.Boolean()),
    sa.column("period_start", sa.DateTime(timezone=True)),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    now = datetime.now(timezone.utc)
    # Generate ids up front so we know the Start plan's id without querying (works offline too).
    plan_ids = {slug: uuid4() for slug, *_ in _PLANS}

    # Timestamps are passed explicitly: the columns' server default is now(), which SQLite lacks.
    op.bulk_insert(_plans_t, [
        {
            "id": plan_ids[slug], "slug": slug, "display_name": name, "is_active": True,
            "price_per_day": ppd, "price_per_month": ppm, "max_users": mu, "max_projects": mp,
            "created_at": now, "updated_at": now,
        }
        for slug, name, ppd, ppm, mu, mp in _PLANS
    ])

    # Put every existing user on the Start plan. Skipped in offline (--sql) mode, which can't SELECT.
    if context.is_offline_mode():
        return
    bind = op.get_bind()
    user_ids = bind.execute(sa.text("SELECT id FROM users")).scalars().all()
    if user_ids:
        op.bulk_insert(_user_plans_t, [
            {
                "id": uuid4(), "user_id": uid, "plan_id": plan_ids["start"], "is_active": True,
                "period_start": now, "created_at": now, "updated_at": now,
            }
            for uid in user_ids
        ])


def downgrade() -> None:
    if context.is_offline_mode():
        op.execute(_user_plans_t.delete())
        op.execute(_plans_t.delete().where(_plans_t.c.slug.in_([p[0] for p in _PLANS])))
        return
    bind = op.get_bind()
    bind.execute(_user_plans_t.delete())
    bind.execute(_plans_t.delete().where(_plans_t.c.slug.in_([p[0] for p in _PLANS])))
