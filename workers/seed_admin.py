"""Seed an admin user on first startup.

Reads ``ADMIN_EMAIL`` / ``ADMIN_PASSWORD`` from env (defaults to
``admin@topinjector.com`` / ``AdminPass123!``).  If the email already
exists as a verified user the task is a no-op — allows re-deploy without side-effect.

The admin gets:
* ``is_admin = True``
* ``is_verified = True``
* ``bonus_credits = MAX_INT64`` (effectively unlimited; daily_billing skips admins).
"""

from os import environ as env

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.session import get_session_cls
from services.auth_service.domain.models import User
from workers.db import run_with_session
import bcrypt

# ---------------------------------------------------------------------------
# Defaults — override via environment variables when running in Docker.
# ---------------------------------------------------------------------------
ADMIN_EMAIL: str = env.get("ADMIN_EMAIL", "admin@topinjector.com")
ADMIN_PASSWORD: str = env.get("ADMIN_PASSWORD", "AdminPass123!")

INT64_MAX = 9_223_372_036_854_775_807  # max value for a BigInt


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def seed_admin(session: AsyncSession) -> dict:
    """Create or update the admin user with infinite credits."""

    result = await session.execute(select(User).where(User.email == ADMIN_EMAIL))
    existing = result.scalar_one_or_none()

    if existing:
        # Already seeded — just ensure flags / balance are correct (re-deploy safety).
        existing.is_admin = True
        existing.is_verified = True
        existing.is_active = True
        existing.bonus_credits = INT64_MAX
        await session.commit()
        return {"action": "updated", "email": ADMIN_EMAIL}

    user = User(
        email=ADMIN_EMAIL,
        password_hash=_hash_password(ADMIN_PASSWORD),
        display_name="Admin",
        is_active=True,
        is_admin=True,
        is_verified=True,
        bonus_credits=INT64_MAX,  # unlimited balance
    )
    session.add(user)
    await session.commit()
    return {"action": "created", "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}


def run_seed_admin() -> dict:
    """Synchronous entry point used by Celery beat / supervisor."""
    return run_with_session(seed_admin)
