"""Queue service routes — push tasks, submit results, list status."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from services.queue_service.domain.models import QueueTask

router = APIRouter(tags=["queue"])


@router.post("/push")
async def push_tasks(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Push tasks to the queue.

    Request body: {\"project_id\": \"...\", \"tasks\": [{\"query_id\", \"click_url\", \"source\", \"geo\"}]}
    Response: {\"queued\": N, \"already_exists\": M}
    """
    queued = 0
    exists = 0
    for task_data in body.get("tasks", []):
        existing = await session.execute(
            select(QueueTask).where(
                QueueTask.click_url == task_data["click_url"],
                QueueTask.status == "pending",
            )
        )
        if existing.scalar_one_or_none():
            exists += 1
            continue
        task = QueueTask(
            project_id=body.get("project_id"),
            query_id=task_data.get("query_id"),
            click_url=task_data["click_url"],
            source=task_data.get("source", "strategy"),
            geo=task_data.get("geo"),
            details=task_data.get("details"),
        )
        session.add(task)
        queued += 1

    await session.commit()
    return {"queued": queued, "already_exists": exists}


@router.get("/")
async def list_tasks(
    project_id: str | None = None,
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """List queue tasks with optional filters.

    Query params: project_id, status
    Response: array of task dicts
    """
    query = select(QueueTask)
    if project_id:
        from uuid import UUID

        query = query.where(QueueTask.project_id == UUID(project_id))
    if status:
        query = query.where(QueueTask.status == status)

    result = await session.execute(query.order_by(QueueTask.created_at))
    tasks = result.scalars().all()

    return [
        {
            "id": str(t.id),
            "status": t.status,
            "source": t.source,
            "click_url": t.click_url,
            "geo": t.geo,
            "created_at": t.created_at.isoformat(),
        }
        for t in tasks
    ]


@router.post("/results")
async def submit_results(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Submit click results from bots.

    Request body: {\"results\": [{\"task_id\", \"status\", \"position\"}]}
    Response: {\"updated\": N, \"errors\": []}
    """
    updated = 0
    for r in body.get("results", []):
        task_result = await session.execute(
            select(QueueTask).where(QueueTask.id == r["task_id"])
        )
        task = task_result.scalar_one_or_none()
        if task:
            task.status = r["status"]
            task.position = r.get("position")
            updated += 1

    await session.commit()
    return {"updated": updated, "errors": []}


@router.post("/clear")
async def clear_queue(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Clear all pending tasks for a project."""
    from uuid import UUID

    from sqlalchemy import delete as sql_delete

    result = await session.execute(
        sql_delete(QueueTask).where(
            QueueTask.project_id == UUID(project_id),
            QueueTask.status.in_(["pending", "in_progress"]),
        )
    )
    await session.commit()
    return {"deleted": result.rowcount}
