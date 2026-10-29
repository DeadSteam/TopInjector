"""Seed an admin user on first startup.

Reads ``ADMIN_EMAIL`` / ``ADMIN_PASSWORD`` from env (defaults to
``admin@topinjector.com`` / ``AdminPass123!``).  If the email already
exists as a verified user the task is a no-op — allows re-deploy without side-effect.

The admin gets:
* ``is_admin = True``
* ``is_verified = True``
* ``bonus_credits = MAX_INT64`` (effectively unlimited; daily_billing skips admins).
"""

from logging import getLogger

import bcrypt

logger = getLogger(__name__)

INT64_MAX = 9_223_372_036_854_775_807  # max value for a BigInt


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# ---------------------------------------------------------------------------
# Lazily-read env vars so tests can patch them between module reloads.
# ---------------------------------------------------------------------------
def _admin_email() -> str:
    from os import environ
    return environ.get("ADMIN_EMAIL", "admin@topinjector.com")


def _admin_password() -> str:
    from os import environ
    return environ.get("ADMIN_PASSWORD", "AdminPass123!")


async def seed_admin(session: object) -> dict:
    """Create or update the admin user with infinite credits.

    ``session`` is a SQLAlchemy ``AsyncSession`` provided by the caller.
    Returns a dict describing what happened.
    """
    from sqlalchemy import inspect as sa_inspect, select
    from sqlalchemy.ext.asyncio import AsyncSession

    sess = session  # type: ignore[assignment]
    assert isinstance(sess, AsyncSession), f"expected AsyncSession, got {type(sess)}"

    User = _get_user_model()

    email = _admin_email()
    password = _admin_password()

    # Ensure the users table exists (handles re-deploy when tables are missing).
    bind = sess.get_bind()
    insp = sa_inspect(bind.sync_engine) if hasattr(bind, 'sync_engine') else sa_inspect(bind)
    if not insp.has_table(User.__tablename__):
        from services.models import Base
        async with bind.connect() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.commit()  # type: ignore[attr-defined]

    try:
        result = await sess.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
    except Exception as exc:
        logger.warning("seed_admin query failed (tables may not be ready): %s", exc)
        return {"action": "deferred", "email": email, "reason": str(exc)}

    if existing:
        # Already seeded — ensure flags / balance are correct (re-deploy safety).
        existing.is_admin = True
        existing.is_verified = True
        existing.is_active = True
        existing.bonus_credits = INT64_MAX
        await sess.commit()
        return {"action": "updated", "email": email}

    user = User(
        email=email,
        password_hash=_hash_password(password),
        display_name="Admin",
        is_active=True,
        is_admin=True,
        is_verified=True,
        bonus_credits=INT64_MAX,  # unlimited balance
    )
    sess.add(user)
    await sess.commit()
    return {"action": "created", "email": email, "password": password}


def _get_user_model():
    from services.auth_service.domain.models import User
    return User


def run_seed_admin() -> dict:
    """Synchronous entry point used by Celery beat / supervisor.

    Creates its own async loop and DB engine via ``workers.db.run_with_session``.
    """
    from workers.db import run_with_session as _rws

    # Capture env vars now so test reloads pick them up.
    email = _admin_email()
    password = _admin_password()

    async def _main(session: object) -> dict:  # noqa: ANN202
        return await seed_admin(session)

    return _rws(_main)
