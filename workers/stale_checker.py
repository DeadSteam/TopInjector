"""Stale checker worker — marks in_progress tasks older than 30 min as stuck."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from workers import app
from shared.database.session import async_session_factory


@app.task(name="workers.stale_checker._check_stale_async")
async def _check_stale_async():
    """Async worker that marks in_progress tasks older than 30 min as stuck."""
    session = async_session_factory()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)

        from services.queue_service.domain.models import QueueTask
        result = await session.execute(
            select(QueueTask).where(
                QueueTask.status == "in_progress",
                QueueTask.created_at < cutoff,
            )
        )
        stuck_tasks = result.scalars().all()

        count = 0
        for task in stuck_tasks:
            from sqlalchemy import update as sql_update
            await session.execute(
                sql_update(QueueTask)
                .where(QueueTask.id == task.id)  # type: ignore[attr-defined]
                .values(status="stuck")
            )
            count += 1

        if count > 0:
            await session.commit()
    finally:
        await session.close()

    return {"stuck_marked": count}


@app.task(name="workers.stale_checker.check_stale")
def check_stale():
    """Check for stuck tasks and mark them."""
    return app.send_task("workers.stale_checker._check_stale_async")
