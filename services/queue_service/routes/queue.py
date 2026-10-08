"""Queue service routes — push tasks, submit results, list status."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
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
