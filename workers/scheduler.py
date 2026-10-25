"""Scheduler worker — releases strategy tasks for active projects through the day.

How much is due when is defined in ``services.project_service.strategy`` (daily / hourly /
monthly rules, scheduling window, SCHEDULE_TIMEZONE). Each tick creates only what is due and
not yet created today. Tasks go to the queries with the fewest tasks today relative to their
weight (``daily_clicks``, 1 if unset), and a query never gets a second pending strategy task
while the first hasn't been taken by an agent. Queries whose text contains one of the owner's
stop words (Settings → Словофильтр; case-insensitive substring, so word forms match too) get no
tasks. Projects past ``auto_stop_at`` are switched off.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth_service.domain.models import User
from services.project_service.domain.models import Project, Query
from services.project_service.strategy import due_by, local_day_start, local_now
from services.queue_service.domain.models import QueueTask
from workers import app
from workers.db import run_with_session


async def _schedule_project(session: AsyncSession, project: Project, now: datetime, day_start: datetime) -> int:
    created_today = dict((await session.execute(
        select(QueueTask.query_id, func.count())
        .where(QueueTask.project_id == project.id, QueueTask.source == "strategy", QueueTask.created_at >= day_start)
        .group_by(QueueTask.query_id)
    )).all())
    to_create = due_by(project, local_now(now)) - sum(created_today.values())
    if to_create <= 0:
        return 0

    pending_urls = set((await session.execute(
        select(QueueTask.click_url).where(
            QueueTask.project_id == project.id, QueueTask.status == "pending", QueueTask.source != "proklik"
        )
    )).scalars())
    owner_settings = (await session.execute(
        select(User.messenger_settings).where(User.id == project.user_id)
    )).scalar_one_or_none() or {}
    stop_words = [w.lower() for w in owner_settings.get("stop_words", []) if w]
    candidates = [
        q for q in (await session.execute(select(Query).where(Query.project_id == project.id))).scalars()
        if q.click_url and q.click_url not in pending_urls and not any(w in q.text.lower() for w in stop_words)
    ]

    created = 0
    for _ in range(to_create):
        if not candidates:
            break
        query = min(candidates, key=lambda q: (created_today.get(q.id, 0) / (q.daily_clicks or 1), q.text))
        session.add(QueueTask(
            id=uuid4(), project_id=project.id, query_id=query.id, click_url=query.click_url,
            source="strategy", geo=query.geo or {}, created_at=now,
        ))
        created_today[query.id] = created_today.get(query.id, 0) + 1
        candidates.remove(query)  # one pending task per URL
        created += 1
    return created


async def schedule_strategy_tasks(session: AsyncSession, now: datetime | None = None) -> int:
    """Run one scheduler tick; returns how many tasks were created."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    day_start = local_day_start(now)

    await session.execute(
        update(Project)
        .where(Project.is_active.is_(True), Project.auto_stop_at.isnot(None), Project.auto_stop_at <= now)
        .values(is_active=False)
    )

    projects = (await session.execute(select(Project).where(Project.is_active.is_(True)))).scalars().all()
    created = 0
    for project in projects:
        created += await _schedule_project(session, project, now, day_start)
    await session.commit()
    return created


@app.task(name="workers.scheduler.schedule_daily_tasks")
def schedule_daily_tasks():
    """Beat entry point (every minute)."""
    return {"scheduled": run_with_session(schedule_strategy_tasks)}
