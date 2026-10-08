"""Scheduler worker — generates daily queue tasks from strategy_type."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from workers import app
from shared.database.session import async_session_factory


@app.task(name="workers.scheduler.schedule_daily_tasks")
def schedule_daily_tasks():
    """Generate pending tasks for projects with strategy_type='daily'."""
    async def _run():
        session = async_session_factory()
        try:
            # Find active projects with daily strategy
            result = await session.execute(
                select(QueueTask.project_id)
                .where(QueueTask.status == "pending")
                .distinct()
            )
            scheduled_projects = {r[0] for r in result.all()}

            from services.project_service.domain.models import Project
            projects_result = await session.execute(
                select(Project).where(
                    Project.is_active.is_(True),
                    Project.strategy_type == "daily",
                    ~Project.id.in_(scheduled_projects),
                )
            )
            projects = projects_result.scalars().all()

            for project in projects:
                from services.project_service.repositories.query_repo import QueryRepository
                query_repo = QueryRepository(session)
                queries = await query_repo.get_by_project(project.id)  # type: ignore[arg-type]

                for q in queries[:project.daily_limit]:  # limit per day
                    from services.queue_service.domain.models import QueueTask
                    task = QueueTask(
                        id=uuid4(),
                        project_id=project.id,
                        query_id=q.id if hasattr(q, "id") else None,
                        click_url=q.click_url or "",
                        source="strategy",
                        geo={},
                    )
                    await session.add(task)

            await session.commit()
        finally:
            await session.close()

    _run.__name__ = "schedule_daily_tasks"  # type: ignore[attr-defined]
    return app.send_task("workers.scheduler._schedule_daily_tasks_async")


@app.task(name="workers.scheduler._schedule_daily_tasks_async")
def schedule_hourly_tasks():
    """Generate tasks for hourly strategy projects."""
    return {"scheduled": 0}
