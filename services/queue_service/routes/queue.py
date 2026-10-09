"""Queue service routes — push tasks, submit results, list status, SSE feed."""

import asyncio
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.session import get_session
from services.queue_service.domain.models import QueueTask
from services.queue_service.repositories.task_repo import QueueTaskRepository

router = APIRouter(tags=["queue"])


async def _task_repo(session: AsyncSession = Depends(get_session)) -> QueueTaskRepository:
    return QueueTaskRepository(session)


@router.post("/push")
async def push_tasks(
    body: dict,
    task_repo: QueueTaskRepository = Depends(_task_repo),
):
    """Push tasks to the queue."""
    from uuid import uuid4

    queued = 0
    for task_data in body.get("tasks", []):
        task = QueueTask(
            id=uuid4(),
            project_id=body.get("project_id"),
            query_id=task_data.get("query_id"),
            click_url=task_data["click_url"],
            source=task_data.get("source", "strategy"),
            geo=task_data.get("geo", {}),
        )
        await task_repo.create(task)
        queued += 1
    return {"queued": queued, "already_exists": 0}


@router.get("/")
async def list_tasks(
    project_id: str | None = None,
    status: str | None = None,
    task_repo: QueueTaskRepository = Depends(_task_repo),
):
    """List queue tasks with optional filters."""
    pid = UUID(project_id) if project_id else None
    tasks = await task_repo.get_all(pid, status)
    return [
        {
            "id": str(t.id),
            "status": t.status,
            "source": t.source,
            "click_url": t.click_url,
            "geo": t.geo,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ]


@router.post("/results")
async def submit_results(
    body: dict,
    task_repo: QueueTaskRepository = Depends(_task_repo),
):
    """Submit results from agents."""
    updated = 0
    errors = []
    for r in body.get("results", []):
        result = await task_repo.update_status(
            UUID(r["task_id"]), r["status"], r.get("position")
        )
        if result:
            updated += 1
        else:
            errors.append({"task_id": r.get("task_id"), "error": "not updateable"})
    return {"updated": updated, "errors": errors}


@router.post("/clear")
async def clear_queue(
    project_id: str,
    task_repo: QueueTaskRepository = Depends(_task_repo),
):
    """Clear all pending tasks for a project."""
    deleted = await task_repo.clear_for_project(UUID(project_id))
    return {"deleted": deleted}


# --- Real-time SSE ------------------------------------------------------------ #

@router.get("/feed")
async def queue_feed(
    project_id: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Server-Sent Events feed for real-time queue status updates."""
    async def event_stream():
        last_stats: dict | None = None
        while True:
            try:
                pid = UUID(project_id) if project_id else None
                from sqlalchemy import func, select as sa_select

                query = sa_select(QueueTask.status, func.count())
                if pid:
                    query = query.where(QueueTask.project_id == pid)
                query = query.group_by(QueueTask.status)
                result = await session.execute(query)
                stats_map = {str(r[0]): r[1] for r in result.all()}
                current = {
                    "pending": stats_map.get("pending", 0),
                    "in_progress": stats_map.get("in_progress", 0),
                    "completed": stats_map.get("completed", 0),
                    "not_found": stats_map.get("not_found", 0),
                    "stuck": stats_map.get("stuck", 0),
                }
                if current != last_stats:
                    last_stats = current
                    yield f"data: {__import__('json').dumps({'type': 'stats', 'data': current})}\n\n"
                await asyncio.sleep(3)
            except Exception as e:
                yield f"event: error\ndata: {__import__('json').dumps({'message': str(e)})}\n\n"
                await asyncio.sleep(5)

    from fastapi.responses import StreamingResponse

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@router.get("/stats")
async def get_queue_stats(
    project_id: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Get current queue statistics."""
    query = sa_select(QueueTask.status, func.count())
    if project_id:
        query = query.where(QueueTask.project_id == UUID(project_id))
    query = query.group_by(QueueTask.status)
    result = await session.execute(query)
    stats_map = {str(r[0]): r[1] for r in result.all()}
    return {
        "pending": stats_map.get("pending", 0),
        "in_progress": stats_map.get("in_progress", 0),
        "completed": stats_map.get("completed", 0),
        "not_found": stats_map.get("not_found", 0),
        "stuck": stats_map.get("stuck", 0),
    }


@router.post("/proklik")
async def proklik(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Send instant proklik tasks (manual clicks from the project page)."""
    project_id = UUID(body["project_id"])
    count = body.get("count", 1)
    query_ids: list[str] | None = body.get("query_ids")

    if query_ids:
        # Create proklik tasks for each selected query
        for qid in query_ids:
            n_clicks = body.get("clicks_per_query", 1)
            for _ in range(n_clicks):
                task = QueueTask(
                    id=uuid4(),
                    project_id=project_id,
                    query_id=UUID(qid),
                    click_url="",
                    source="proklik",
                    geo={},
                )
                session.add(task)
    else:
        # Random queries — generate N proklik tasks
        for _ in range(count):
            task = QueueTask(
                id=uuid4(),
                project_id=project_id,
                query_id=None,
                click_url="",
                source="proklik",
                geo={},
            )
            session.add(task)

    await session.commit()
    return {"created": count, "status": "queued"}


@router.get("/stats/source")
async def get_queue_stats_by_source(
    project_id: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Get queue statistics broken down by source (strategy/autoburst/proklik)."""
    query = sa_select(QueueTask.source, func.count()).where(QueueTask.status == "completed")
    if project_id:
        query = query.where(QueueTask.project_id == UUID(project_id))
    query = query.group_by(QueueTask.source)
    result = await session.execute(query)
    return {r[0]: r[1] for r in result.all()}
