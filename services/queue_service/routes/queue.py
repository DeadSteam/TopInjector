"""Queue service routes — push tasks, submit results, list status, SSE feed."""

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.access import (
    accessible_project_ids,
    check_project_access,
    editable_project_ids,
    request_user_id,
)
from shared.database.session import get_session
from shared.validation import parse_uuid, require_fields
from services.queue_service.domain.models import PENDING_OVERDUE_AFTER, QueueTask, TaskStatus
from services.queue_service.repositories.task_repo import QueueTaskRepository, task_filters

logger = logging.getLogger(__name__)

# Every route requires auth; each one limits itself to projects the caller may access.
router = APIRouter(tags=["queue"], dependencies=[Depends(request_user_id)])

# Canonical integrations — mirrors project_service for label resolution
_CANONICAL_INTEGRATIONS: list[dict] = [
    {"key": "default", "label": "Default (без интеграции)", "description": "Стандартная настройка без внешней интеграции"},
    {"key": "google-search-console", "label": "Google Search Console", "description": "Интеграция с Google Search Console"},
    {"key": "yandex-webmaster", "label": "Яндекс Вебмастер", "description": "Интеграция с Яндекс.Вебмастер"},
    {"key": "custom", "label": "Custom URL", "description": "Произвольный URL для индексации"},
]


def _resolve_integration_label(key: str) -> str:
    """Resolve integration key to a human-readable label."""
    for integ in _CANONICAL_INTEGRATIONS:
        if integ["key"] == key:
            return integ["label"]
    return key  # fallback: show the raw key


async def _task_repo(session: AsyncSession = Depends(get_session)) -> QueueTaskRepository:
    return QueueTaskRepository(session)


# Upper bound on how many tasks a single proklik request may create.
MAX_PROKLIK_TASKS = 10_000


def _bounded_count(raw: object, field: str) -> int:
    """Parse a positive task count, rejecting non-ints and anything over MAX_PROKLIK_TASKS (422)."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"{field} must be an integer")
    if value < 1 or value > MAX_PROKLIK_TASKS:
        raise HTTPException(status_code=422, detail=f"{field} must be between 1 and {MAX_PROKLIK_TASKS}")
    return value


@router.post("/push")
async def push_tasks(
    body: dict,
    user_id: UUID = Depends(request_user_id),
    task_repo: QueueTaskRepository = Depends(_task_repo),
    session: AsyncSession = Depends(get_session),
):
    """Push tasks to the queue."""
    require_fields(body, "project_id")
    project_id = (await check_project_access(session, body["project_id"], user_id, write=True)).id

    from services.project_service.domain.models import Query as _QueryModel

    project_query_ids = set(
        (await session.execute(sa_select(_QueryModel.id).where(_QueryModel.project_id == project_id))).scalars()
    )
    queued = 0
    for task_data in body.get("tasks", []):
        query_id = parse_uuid(task_data["query_id"], "query_id") if task_data.get("query_id") else None
        if query_id is not None and query_id not in project_query_ids:
            raise HTTPException(status_code=422, detail="query_id does not belong to this project")
        task = QueueTask(
            id=uuid4(),
            project_id=project_id,
            query_id=query_id,
            click_url=task_data["click_url"],
            source=task_data.get("source", "strategy"),
            geo=task_data.get("geo", {}),
        )
        await task_repo.create(task)
        queued += 1
    await session.commit()
    return {"queued": queued, "already_exists": 0}


@router.get("/")
async def list_tasks(
    project_id: str | None = None,
    status: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    integration: str | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
    user_id: UUID = Depends(request_user_id),
    task_repo: QueueTaskRepository = Depends(_task_repo),
    session: AsyncSession = Depends(get_session),
):
    """Newest queue tasks first (at most ``limit``), filtered by project, status, creation date and integration."""
    pid = (await check_project_access(session, project_id, user_id)).id if project_id else None
    tasks = await task_repo.get_all(
        pid, status, from_date, to_date, integration, project_ids=accessible_project_ids(user_id), limit=limit
    )
    return [
        {
            "id": str(t.id),
            "project_id": str(t.project_id),
            "project_name": t.project.name,
            "query_id": str(t.query_id) if t.query_id else None,
            "status": t.status,
            "source": t.source,
            "click_url": t.click_url,
            "geo": t.geo,
            "position": t.position,
            "details": t.details,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in tasks
    ]


@router.post("/results")
async def submit_results(
    body: dict,
    user_id: UUID = Depends(request_user_id),
    task_repo: QueueTaskRepository = Depends(_task_repo),
    session: AsyncSession = Depends(get_session),
):
    """Submit results from agents."""
    updated = 0
    errors = []
    for r in body.get("results", []):
        require_fields(r, "task_id", "status")
        if r["status"] not in {s.value for s in TaskStatus}:
            raise HTTPException(status_code=422, detail=f"Unknown status: {r['status']}")
        result = await task_repo.update_status(
            parse_uuid(r["task_id"], "task_id"), r["status"], r.get("position"),
            project_ids=editable_project_ids(user_id), details=r.get("details"),
        )
        if result:
            updated += 1
        else:
            errors.append({"task_id": r.get("task_id"), "error": "not updateable"})
    await session.commit()
    return {"updated": updated, "errors": errors}


@router.post("/clear")
async def clear_queue(
    project_id: str,
    user_id: UUID = Depends(request_user_id),
    task_repo: QueueTaskRepository = Depends(_task_repo),
    session: AsyncSession = Depends(get_session),
):
    """Clear all pending tasks for a project."""
    project = await check_project_access(session, project_id, user_id, write=True)
    deleted = await task_repo.clear_for_project(project.id)
    await session.commit()
    return {"deleted": deleted}


# --- Real-time SSE ------------------------------------------------------------ #

@router.get("/feed")
async def queue_feed(
    project_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    integration: str | None = None,
    user_id: UUID = Depends(request_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Server-Sent Events feed for real-time queue status updates."""
    pid = (await check_project_access(session, project_id, user_id)).id if project_id else None

    async def event_stream():
        last_stats: dict | None = None
        while True:
            try:
                query = sa_select(QueueTask.status, func.count()).where(
                    QueueTask.project_id.in_(accessible_project_ids(user_id)),
                    *task_filters(pid, from_date, to_date, integration),
                )
                query = query.group_by(QueueTask.status)
                result = await session.execute(query)
                stats_map = {str(r[0]): r[1] for r in result.all()}
                await session.rollback()  # end the read so the connection goes back to the pool between polls
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
            except Exception:
                # Don't leak internal error details to the client; log and send a generic message.
                logger.exception("queue feed error for user %s", user_id)
                yield f"event: error\ndata: {__import__('json').dumps({'message': 'stream error'})}\n\n"
                await asyncio.sleep(5)

    from fastapi.responses import StreamingResponse

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@router.get("/stats")
async def get_queue_stats(
    project_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    integration: str | None = None,
    user_id: UUID = Depends(request_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Task counts per status, with the same filters as the task list."""
    pid = (await check_project_access(session, project_id, user_id)).id if project_id else None
    query = sa_select(QueueTask.status, func.count()).where(
        QueueTask.project_id.in_(accessible_project_ids(user_id)),
        *task_filters(pid, from_date, to_date, integration),
    )
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
    user_id: UUID = Depends(request_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Send instant proklik tasks (manual clicks from the project page)."""
    if "project_id" not in body:
        raise HTTPException(status_code=422, detail="project_id is required")
    from services.project_service.domain.models import Query as _QueryModel

    project_id = (await check_project_access(session, body["project_id"], user_id, write=True)).id
    query_ids: list[str] | None = body.get("query_ids")

    # Bound the request so one call can't enqueue an unbounded number of tasks.
    clicks_per_query = _bounded_count(body.get("clicks_per_query", 1), "clicks_per_query")
    count = _bounded_count(body.get("count", 1), "count")

    stmt = sa_select(_QueryModel).where(_QueryModel.project_id == project_id)
    if query_ids:
        stmt = stmt.where(_QueryModel.id.in_([parse_uuid(q, "query_id") for q in query_ids]))
    queries = (await session.execute(stmt)).scalars().all()
    if not queries:
        raise HTTPException(status_code=400, detail="В проекте нет запросов для проклика")

    if query_ids:
        # clicks_per_query tasks for each selected query
        picks = [q for q in queries for _ in range(clicks_per_query)]
    else:
        # N tasks on random queries of the project
        picks = random.choices(queries, k=count)

    for q in picks:
        session.add(QueueTask(
            id=uuid4(),
            project_id=project_id,
            query_id=q.id,
            click_url=q.click_url or "",
            source="proklik",
            geo=q.geo or {},
        ))

    await session.commit()
    return {"created": len(picks), "status": "queued"}


@router.get("/stats/source")
async def get_queue_stats_by_source(
    project_id: str | None = None,
    user_id: UUID = Depends(request_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get queue statistics broken down by source (strategy/autoburst/proklik)."""
    query = sa_select(QueueTask.source, func.count()).where(
        QueueTask.status == "completed",
        QueueTask.project_id.in_(accessible_project_ids(user_id)),
    )
    if project_id:
        project = await check_project_access(session, project_id, user_id)
        query = query.where(QueueTask.project_id == project.id)
    query = query.group_by(QueueTask.source)
    result = await session.execute(query)
    return {r[0]: r[1] for r in result.all()}


@router.get("/dashboard-stats")
async def get_dashboard_stats(
    user_id: UUID = Depends(request_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Status bar numbers across the user's own projects.

    overdue: pending tasks waiting longer than PENDING_OVERDUE_AFTER; today_completed: tasks
    finished since local midnight; today_planned: today's strategy quotas of active projects;
    balance: sum of project balances in rubles.
    """
    from services.project_service.domain.models import Project
    from services.project_service.strategy import local_day_start, local_now, quota_for_day

    projects = (await session.execute(sa_select(Project).where(Project.user_id == user_id))).scalars().all()
    if not projects:
        return {"overdue": 0, "today_planned": 0, "today_completed": 0, "balance": 0}
    pid_list = [p.id for p in projects]
    now = datetime.now(timezone.utc)

    overdue = (await session.execute(
        sa_select(func.count(QueueTask.id)).where(
            QueueTask.project_id.in_(pid_list),  # type: ignore[arg-type]
            QueueTask.status == "pending",
            QueueTask.created_at < now - PENDING_OVERDUE_AFTER,
        )
    )).scalar() or 0

    today_completed = (await session.execute(
        sa_select(func.count(QueueTask.id)).where(
            QueueTask.project_id.in_(pid_list),  # type: ignore[arg-type]
            QueueTask.status == "completed",
            QueueTask.updated_at >= local_day_start(now),  # when the result came in
        )
    )).scalar() or 0

    today = local_now(now)
    return {
        "overdue": overdue,
        "today_planned": sum(quota_for_day(p, today) for p in projects if p.is_active),
        "today_completed": today_completed,
        "balance": round(sum(p.balance_credits or 0 for p in projects) / 100, 2),
    }


@router.get("/dashboard-servers")
async def get_dashboard_servers(
    user_id: UUID = Depends(request_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Per-integration panels of the dashboard over the user's active projects.

    pending: tasks waiting now; speed_per_15min / completed_24h / not_found_24h: results that came in
    during the last 15 minutes / 24 hours; hourly_bars: completed results of the last 24 hours by local hour.
    Projects without an integration are grouped under "default".
    """
    from services.project_service.domain.models import Project
    from services.project_service.strategy import local_now

    now = datetime.now(timezone.utc)
    integration = Project.integrations["integration_type"].as_string()
    scope = (Project.user_id == user_id, Project.is_active.is_(True))

    pending_rows = await session.execute(
        sa_select(integration, func.count(QueueTask.id))
        .join(Project, QueueTask.project_id == Project.id)
        .where(*scope, QueueTask.status == TaskStatus.PENDING)
        .group_by(integration)
    )
    finished_rows = await session.execute(
        sa_select(integration, QueueTask.status, QueueTask.updated_at)  # updated_at = when the result came in
        .join(Project, QueueTask.project_id == Project.id)
        .where(
            *scope,
            QueueTask.status.in_((TaskStatus.COMPLETED, TaskStatus.NOT_FOUND)),
            QueueTask.updated_at >= now - timedelta(hours=24),
        )
    )

    servers: dict[str, dict] = {}

    def panel(key: str | None) -> dict:
        key = key or "default"
        if key not in servers:
            servers[key] = {
                "integration": key, "label": _resolve_integration_label(key), "pending": 0,
                "speed_per_15min": 0, "completed_24h": 0, "not_found_24h": 0, "hourly_bars": [0] * 24,
            }
        return servers[key]

    for key, count in pending_rows.all():
        panel(key)["pending"] += count
    for key, status, finished_at in finished_rows.all():
        stats = panel(key)
        if status == TaskStatus.NOT_FOUND:
            stats["not_found_24h"] += 1
            continue
        if finished_at.tzinfo is None:  # SQLite drops the offset
            finished_at = finished_at.replace(tzinfo=timezone.utc)
        stats["completed_24h"] += 1
        stats["speed_per_15min"] += finished_at >= now - timedelta(minutes=15)
        stats["hourly_bars"][local_now(finished_at).hour] += 1

    return sorted(servers.values(), key=lambda s: s["integration"])


@router.get("/dashboard-users")
async def get_dashboard_users(
    user_id: UUID = Depends(request_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Dashboard 'Users' tab data: current user's plan, projects count, and usage ratios."""
    from services.project_service.domain.models import Project
    from services.project_service.domain.plans import Plan, UserPlan

    # Get the current user's plan
    up = (await session.execute(
        sa_select(UserPlan).where(UserPlan.user_id == user_id, UserPlan.is_active.is_(True))
    )).scalar_one_or_none()

    plan_info = None
    if up:
        plan = await session.get(Plan, up.plan_id)
        plan_info = {
            "slug": plan.slug,
            "display_name": plan.display_name,
            "max_projects": plan.max_projects,
            "price_per_month": plan.price_per_month,
            "is_free_tier": plan.slug == "start",
        }

    # Count all projects (not just active)
    project_count = (await session.execute(
        sa_select(func.count(Project.id)).where(Project.user_id == user_id)
    )).scalar() or 0

    return {
        "plan": plan_info,
        "project_count": project_count,
    }


@router.get("/dashboard-users")
async def get_dashboard_users(
    user_id: UUID = Depends(request_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Dashboard 'Users' tab data: current user's plan, project count, and usage ratios."""
    from services.project_service.domain.models import Project
    from services.project_service.domain.plans import Plan, UserPlan

    # Get the current user's plan
    up = (await session.execute(
        sa_select(UserPlan).where(UserPlan.user_id == user_id, UserPlan.is_active.is_(True))
    )).scalar_one_or_none()

    plan_info = None
    if up:
        plan = await session.get(Plan, up.plan_id)
        plan_info = {
            "slug": plan.slug,
            "display_name": plan.display_name,
            "max_projects": plan.max_projects,
            "price_per_month": plan.price_per_month,
            "is_free_tier": plan.slug == "start",
        }

    # Count all projects (not just active)
    project_count = (await session.execute(
        sa_select(func.count(Project.id)).where(Project.user_id == user_id)
    )).scalar() or 0

    return {
        "plan": plan_info,
        "project_count": project_count,
    }


@router.get("/dashboard-users")
async def get_dashboard_users(
    user_id: UUID = Depends(request_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Dashboard 'Users' tab data: current user's plan, users count, bonus credits, usage ratios.

    Returns plan info, total projects, active users (for team plans), and live counters.
    """
    from services.auth_service.domain.models import User
    from services.project_service.domain.models import Project
    from services.project_service.domain.plans import Plan, UserPlan
    from shared.config import settings

    # Get the current user's plan
    up = (await session.execute(
        sa_select(UserPlan).where(UserPlan.user_id == user_id, UserPlan.is_active.is_(True))
    )).scalar_one_or_none()

    plan_info = None
    if up:
        plan = await session.get(Plan, up.plan_id)
        plan_info = {
            "slug": plan.slug,
            "display_name": plan.display_name,
            "max_projects": plan.max_projects,
            "price_per_month": plan.price_per_month,
            "is_free_tier": plan.slug == "start",
        }

    # Count all projects (not just active)
    project_count = (await session.execute(
        sa_select(func.count(Project.id)).where(Project.user_id == user_id)
    )).scalar() or 0

    return {
        "plan": plan_info,
        "project_count": project_count,
    }
