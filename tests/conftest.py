"""Shared fixtures: in-memory SQLite database and an HTTP client bound to the app."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from main import create_app
from services.models import Base
from shared.database.session import get_session


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(session_factory):
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def app_fixture(session_factory):
    """FastAPI app with session override and exposed session_factory for test helpers."""
    app = create_app()

    async def _override_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    app.state.session_factory = session_factory
    return app


@pytest_asyncio.fixture
async def client(app_fixture):
    async with AsyncClient(transport=ASGITransport(app=app_fixture), base_url="http://test") as client:
        yield client


PASSWORD = "correct-horse-42"


async def register(client: AsyncClient, email: str = "owner@example.com") -> dict[str, str]:
    """Register a user and return Authorization headers for them."""
    resp = await client.post(
        "/api/auth/register", json={"email": email, "password": PASSWORD, "display_name": "Owner"}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def auth_headers(client) -> dict[str, str]:
    return await register(client)
