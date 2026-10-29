"""Tests for the seed-admin startup worker."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine
from unittest.mock import patch

from services.auth_service.domain.models import User


def enable_fks(engine):
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def _make_db():
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    enable_fks(eng)
    return eng


async def test_seed_admin_creates_user():
    """A non-existing email should produce a new verified admin."""

    with patch.dict("os.environ", {"ADMIN_EMAIL": "newuser@dev.local", "ADMIN_PASSWORD": "DevP4ss!"}):
        import importlib
        import workers.seed_admin as mod
        importlib.reload(mod)

    eng = _make_db()
    async with eng.begin() as conn:
        await conn.run_sync(User.metadata.create_all)

    factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    result = mod.run_seed_admin()

    assert result["action"] == "created"
    assert result["email"] == "newuser@dev.local"

    async with factory() as sess:
        u = (await sess.execute(select(User).where(User.email == "newuser@dev.local"))).scalar_one_or_none()
    assert u is not None
    assert u.is_admin is True
    assert u.is_verified is True
    assert u.bonus_credits == 9_223_372_036_854_775_807


async def test_seed_admin_updates_existing_non_admin():
    """An existing non-admin user should become admin with infinite balance."""

    eng = _make_db()
    async with eng.begin() as conn:
        await conn.run_sync(User.metadata.create_all)

    factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        old_user = User(email="old@example.com", password_hash="$2b$12$x", display_name="Old", is_admin=False, bonus_credits=0)
        sess.add(old_user)
        await sess.commit()

    with patch.dict("os.environ", {"ADMIN_EMAIL": "old@example.com"}):
        import importlib
        import workers.seed_admin as mod
        importlib.reload(mod)
        result = mod.run_seed_admin()

    assert result["action"] == "updated"

    async with factory() as sess:
        u = (await sess.execute(select(User).where(User.email == "old@example.com"))).scalar_one_or_none()
    assert u is not None
    assert u.is_admin is True
    assert u.is_verified is True
    assert u.bonus_credits == 9_223_372_036_854_775_807


async def test_seed_admin_updates_existing_admin():
    """An existing verified admin should be updated to INT64_MAX (idempotent)."""

    eng = _make_db()
    async with eng.begin() as conn:
        await conn.run_sync(User.metadata.create_all)

    factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    admin_id = None
    async with factory() as sess:
        admin = User(email="admin@topinjector.com", password_hash="$2b$12$x", is_admin=True, is_verified=True, bonus_credits=1000)
        sess.add(admin)
        await sess.commit()
        admin_id = admin.id

    with patch.dict("os.environ", {"ADMIN_EMAIL": "admin@topinjector.com"}):
        import importlib
        import workers.seed_admin as mod
        importlib.reload(mod)
        result = mod.run_seed_admin()

    assert result["action"] == "updated"

    async with factory() as sess:
        u = (await sess.execute(select(User).where(User.id == admin_id))).scalar_one_or_none()
    assert u.bonus_credits == 9_223_372_036_854_775_807
