"""Queue service routes — push tasks, submit results, list status, SSE feed."""

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select as sa_select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.jwt_utils import decode_access_token
from shared.config import settings
from shared.database.session import get_session
from services.auth_service.domain.models import User
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
    from_date: str | None = None,
    to_date: str | None = None,
    task_repo: QueueTaskRepository = Depends(_task_repo),
):
    """List queue tasks with optional filters including date range."""
    pid = UUID(project_id) if project_id else None
    tasks = await task_repo.get_all(pid, status, from_date, to_date)
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
    from_date: str | None = None,
    to_date: str | None = None,
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
                if from_date:
                    try:
                        fd = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc)
                        query = query.where(QueueTask.created_at >= fd)
                    except (ValueError, TypeError):
                        pass
                if to_date:
                    try:
                        td = datetime.fromisoformat(to_date).replace(tzinfo=timezone.utc)
                        query = query.where(QueueTask.created_at <= td)
                    except (ValueError, TypeError):
                        pass
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


async def _user_id_from_request(request: Request) -> UUID | None:
    """Extract user_id from Authorization header without raising 401."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    return decode_access_token(token)


@router.get("/dashboard-stats")
async def get_dashboard_stats(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Aggregate dashboard stats across all user projects: overdue count, today's planned/completed, balance."""
    from services.project_service.domain.models import Project

    user_id = await _user_id_from_request(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Get all project IDs for this user
    projects_result = await session.execute(
        select(Project.id).where(Project.user_id == user_id)
    )
    project_ids = [r[0] for r in projects_result.fetchall()]
    if not project_ids:
        return {
            "overdue": 0,
            "today_planned": 0,
            "today_completed": 0,
            "balance": 0,
        }

    pid_list = [UUID(pid) for pid in project_ids]

    # Overdue count: pending tasks with pending_check_at < now
    now_utc = datetime.now(timezone.utc)
    overdue_result = await session.execute(
        sa_select(func.count(QueueTask.id))
        .where(
            and_(
                QueueTask.project_id.in_(pid_list),  # type: ignore[arg-type]
                QueueTask.status == "pending",
                QueueTask.pending_check_at < now_utc,
            )
        )
    )
    overdue = overdue_result.scalar() or 0

    # Today's completed tasks
    today_start = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)
    today_completed_result = await session.execute(
        sa_select(func.count(QueueTask.id))
        .where(
            and_(
                QueueTask.project_id.in_(pid_list),  # type: ignore[arg-type]
                QueueTask.status == "completed",
                QueueTask.created_at >= today_start,  # type: ignore[attr-defined]
            )
        )
    )
    today_completed = today_completed_result.scalar() or 0

    # Total balance across all user projects (in rubles)
    from services.project_service.domain.models import BalanceTransaction

    bal_result = await session.execute(
        sa_select(func.coalesce(func.sum(Project.balance_credits), 0))
        .where(Project.user_id == user_id)
    )
    balance_kopeks = bal_result.scalar() or 0
    balance = round(balance_kopeks / 100, 2)

    return {
        "overdue": overdue,
        "today_planned": today_completed * 2,  # rough estimate — double completed as rough planned
        "today_completed": today_completed,
        "balance": balance,
    }
