"""Stale checker worker — marks tasks stuck in_progress for over 30 min as stuck."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from services.queue_service.domain.models import QueueTask
from workers import app
from workers.db import run_with_session

STALE_AFTER = timedelta(minutes=30)


async def mark_stale_tasks(session: AsyncSession) -> int:
    """Mark in_progress tasks not updated for STALE_AFTER as stuck; return how many."""
    cutoff = datetime.now(timezone.utc) - STALE_AFTER
    result = await session.execute(
        update(QueueTask)
        .where(QueueTask.status == "in_progress", QueueTask.updated_at < cutoff)
        .values(status="stuck")
    )
    await session.commit()
    return result.rowcount


@app.task(name="workers.stale_checker.check_stale")
def check_stale():
    """Check for stuck tasks and mark them."""
    return {"stuck_marked": run_with_session(mark_stale_tasks)}
