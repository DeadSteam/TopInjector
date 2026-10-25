"""Run async DB work from synchronous Celery tasks."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from shared.config.settings import settings

T = TypeVar("T")


def run_with_session(fn: Callable[[AsyncSession], Awaitable[T]]) -> T:
    """Execute ``fn(session)`` in a fresh event loop and return its result.

    Celery tasks are synchronous, so each call gets its own ``asyncio.run`` loop.
    A throwaway NullPool engine is used because pooled asyncpg connections are
    bound to the loop that created them and can't be reused by the next call.
    """

    async def _main() -> T:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                return await fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(_main())
