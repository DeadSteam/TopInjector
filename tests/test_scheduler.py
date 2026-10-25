"""Strategy scheduler: how many tasks a project gets released by a given moment."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest_asyncio
from sqlalchemy import func, select

from workers.scheduler import schedule_strategy_tasks

MSK = ZoneInfo("Europe/Moscow")


def at(hour: int, minute: int = 0, day: int = 15) -> datetime:
    """A moment in Moscow time (September has 30 days)."""
    return datetime(2026, 9, day, hour, minute, tzinfo=MSK)


@pytest_asyncio.fixture
async def make_project(session_factory):
    from services.auth_service.domain.models import User
    from services.project_service.domain.models import Project, Query

    async def _make(*, strategy="daily", limit=10, queries=6, window=("08:00", "18:00"), weights=None, stop_words=None, **extra):
        async with session_factory() as session:
            user = User(email=f"{uuid4()}@example.com", password_hash="x", messenger_settings={"stop_words": stop_words or []})
            session.add(user)
            await session.flush()
            project = Project(
                user_id=user.id, name="Sched", domain="sched.example.com", strategy_type=strategy, daily_limit=limit,
                scheduling_window={"start": window[0], "end": window[1]} if window else None, **extra,
            )
            session.add(project)
            await session.flush()
            for i in range(queries):
                session.add(Query(project_id=project.id, text=f"q{i}", click_url=f"https://s.example.com/?q={i}",
                                  daily_clicks=(weights or {}).get(i, 0)))
            await session.commit()
            return project.id

    return _make


async def _run(session_factory, now: datetime) -> int:
    async with session_factory() as session:
        return await schedule_strategy_tasks(session, now)


async def _tasks(session_factory, project_id):
    from services.queue_service.domain.models import QueueTask

    async with session_factory() as session:
        return (await session.execute(select(QueueTask).where(QueueTask.project_id == project_id))).scalars().all()


async def test_daily_releases_evenly_through_window(session_factory, make_project):
    pid = await make_project(limit=10)
    assert await _run(session_factory, at(13)) == 5          # half of 08:00–18:00 elapsed
    assert await _run(session_factory, at(13)) == 0          # nothing new is due yet
    tasks = await _tasks(session_factory, pid)
    assert {t.source for t in tasks} == {"strategy"} and all(t.click_url.startswith("https://s.example.com/") for t in tasks)


async def test_nothing_before_window(session_factory, make_project):
    await make_project(limit=10)
    assert await _run(session_factory, at(7, 59)) == 0


async def test_hourly_releases_whole_hour_batches(session_factory, make_project):
    await make_project(strategy="hourly", limit=10, queries=10)
    assert await _run(session_factory, at(8, 30)) == 1        # first of 10 window hours
    assert await _run(session_factory, at(12, 10)) == 4       # 5 hours started → 5 total


async def test_monthly_limit_is_split_across_days(session_factory, make_project):
    await make_project(strategy="monthly", limit=300, queries=20)
    assert await _run(session_factory, at(18)) == 10          # 300 / 30 days, whole window elapsed


async def test_one_pending_task_per_query(session_factory, make_project):
    await make_project(limit=10, queries=2)
    assert await _run(session_factory, at(18)) == 2


async def test_heavier_queries_get_more_tasks(session_factory, make_project):
    from services.queue_service.domain.models import QueueTask

    pid = await make_project(limit=8, queries=2, weights={0: 3, 1: 1})
    released = 0
    for hour in range(9, 19):  # agents finish everything between ticks
        released += await _run(session_factory, at(hour))
        async with session_factory() as session:
            for t in (await session.execute(select(QueueTask).where(QueueTask.project_id == pid))).scalars():
                t.status = "completed"
            await session.commit()
    tasks = await _tasks(session_factory, pid)
    by_query = sorted(sum(1 for t in tasks if t.click_url.endswith(f"q={i}")) for i in range(2))
    assert released == 8 and by_query == [2, 6]


async def test_inactive_and_expired_projects_get_nothing(session_factory, make_project):
    from services.project_service.domain.models import Project

    await make_project(limit=10, is_active=False)
    expired = await make_project(limit=10, auto_stop_at=at(12).astimezone(timezone.utc))
    assert await _run(session_factory, at(13)) == 0
    async with session_factory() as session:
        assert (await session.get(Project, expired)).is_active is False  # auto-stop applied


async def test_tasks_from_previous_day_dont_count(session_factory, make_project):
    pid = await make_project(limit=4, queries=4)
    assert await _run(session_factory, at(18, day=14)) == 4
    from services.queue_service.domain.models import QueueTask

    async with session_factory() as session:
        for t in (await session.execute(select(QueueTask).where(QueueTask.project_id == pid))).scalars():
            t.status = "completed"
        await session.commit()
    assert await _run(session_factory, at(18, day=15)) == 4


async def test_queries_with_owner_stop_words_get_no_tasks(session_factory, make_project):
    from services.project_service.domain.models import Query

    pid = await make_project(limit=10, queries=3, stop_words=["бесплатн"])
    async with session_factory() as session:
        session.add(Query(project_id=pid, text="Окна БЕСПЛАТНО", click_url="https://s.example.com/?q=free"))
        await session.commit()

    await _run(session_factory, at(18))
    urls = {t.click_url for t in await _tasks(session_factory, pid)}
    assert urls == {f"https://s.example.com/?q={i}" for i in range(3)}  # the stop-word query is left out
