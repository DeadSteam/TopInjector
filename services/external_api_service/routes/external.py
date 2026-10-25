"""External API routes (GhostLab-compatible). Base URL: /api/external/v1/ Auth: X-Auth-Token header.

Every token is bound to one project; all token-authenticated routes act on that project only.
"""

from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.jwt_utils import get_current_user
from shared.database.session import get_session
from shared.validation import ensure_safe_url, parse_uuid
from services.project_service.balance import add_balance, balance_payload, set_balance
from services.project_service.domain.models import Project, ProjectToken, Query
from services.project_service.search_urls import search_click_url
from services.queue_service.domain.models import QueueTask, TaskSource, TaskStatus

router = APIRouter(tags=["external-api"])

_TASK_STATUSES = {s.value for s in TaskStatus}
_TASK_SOURCES = {s.value for s in TaskSource}


async def _get_project_by_token(
    x_auth_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> Project:
    """Validate X-Auth-Token against project_tokens table and return the token's Project.

    Inactive projects are still returned so a client can re-activate them; they just get no tasks.
    """
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="Missing X-Auth-Token header")

    result = await session.execute(select(ProjectToken).where(ProjectToken.token_string == x_auth_token))
    token_record = result.scalar_one_or_none()
    if not token_record:
        raise HTTPException(status_code=401, detail="Invalid API token")
    if token_record.project_id is None:
        raise HTTPException(status_code=401, detail="API token is not bound to a project")

    project = await session.get(Project, token_record.project_id)
    if not project:
        raise HTTPException(status_code=401, detail="Project not found")
    return project


def _ensure_same_project(project: Project, project_id: str | None) -> None:
    """A token may only address its own project; anything else looks like it doesn't exist."""
    if project_id and project_id != str(project.id):
        raise HTTPException(status_code=404, detail="Project not found")


def _task_json(task: QueueTask, query_text: str | None = None) -> dict:
    return {
        "id": str(task.id),
        "status": task.status,
        "source": task.source,
        "query_id": str(task.query_id) if task.query_id else None,
        "query_text": query_text,
        "click_url": task.click_url,
        "geo": task.geo,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


@router.get("/health")
async def health():
    """Availability check for mobile clients."""
    return {"status": "ok"}


# --- Projects --------------------------------------------------------------- #

@router.post("/projects")
async def create_project(
    body: dict,
    user = Depends(get_current_user),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """Create a new project. Authenticated via JWT (a project token can only exist after the project)."""
    if not body.get("name") or not body.get("domain"):
        raise HTTPException(status_code=422, detail="Required field(s): name, domain")
    project = Project(
        user_id=user.id,  # type: ignore[attr-defined]
        name=body["name"],
        domain=body["domain"],
        region=body.get("region", "ru"),
        strategy_type=body.get("strategy_type", "daily"),
        daily_limit=body.get("daily_limit", 500),
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return {"id": str(project.id), "name": project.name, "domain": project.domain}


@router.get("/projects")
async def list_projects(
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """List the project bound to the API token."""
    queries_count = (await session.execute(
        select(func.count()).select_from(Query).where(Query.project_id == project.id)
    )).scalar() or 0
    queue_size = (await session.execute(
        select(func.count()).select_from(QueueTask).where(QueueTask.project_id == project.id, QueueTask.status == "pending")
    )).scalar() or 0
    return {
        "projects": [{
            "id": str(project.id),
            "name": project.name,
            "domain": project.domain,
            "region": project.region or "",
            "strategy_type": project.strategy_type,
            "daily_limit": project.daily_limit,
            "is_active": project.is_active,
            "queries_count": queries_count,
            "queue_size": queue_size,
        }],
    }


@router.put("/projects/{project_id}")
async def update_project(
    project_id: str,
    body: dict,
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """Update the token's project."""
    _ensure_same_project(project, project_id)
    for key in ("name", "domain", "region", "strategy_type", "daily_limit"):
        if key in body:
            setattr(project, key, body[key])  # type: ignore[attr-defined]

    await session.commit()
    return {"id": str(project.id), "updated": True}


@router.patch("/projects/{project_id}/status")
async def update_project_status(
    project_id: str,
    body: dict,
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """Toggle project active status."""
    _ensure_same_project(project, project_id)
    project.is_active = bool(body.get("is_active", True))  # type: ignore[attr-defined]

    await session.commit()
    return {"id": str(project.id), "is_active": project.is_active}  # type: ignore[attr-defined]


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """Delete the token's project."""
    _ensure_same_project(project, project_id)
    await session.delete(project)  # type: ignore[arg-type]
    await session.commit()
    return {"deleted": True}


# --- Terms ------------------------------------------------------------------ #

@router.post("/terms/upsert")
async def upsert_terms(
    body: dict,
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """Bulk upsert keyword queries, matched by text.

    Existing queries keep their ids (and so their task and position history); queries not
    mentioned are left alone.
    """
    existing = {
        q.text: q
        for q in (await session.execute(select(Query).where(Query.project_id == project.id))).scalars()
    }

    created = updated = 0
    for item in body.get("queries", []):
        text = (item.get("text") or "").strip()
        if not text:
            continue
        ensure_safe_url(item.get("url"), "url")
        ensure_safe_url(item.get("click_url"), "click_url")
        query = existing.get(text)
        if query is None:
            query = Query(project_id=project.id, text=text, click_url=search_click_url(text))
            session.add(query)
            existing[text] = query
            created += 1
        else:
            updated += 1
        for key in ("url", "click_url", "geo", "daily_clicks"):
            if item.get(key) is not None:
                setattr(query, key, item[key])

    await session.commit()
    return {"created": created, "updated": updated}


@router.get("/terms")
async def list_terms(
    project_id: str = "",
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """List queries of the token's project."""
    _ensure_same_project(project, project_id)
    queries = (await session.execute(select(Query).where(Query.project_id == project.id))).scalars().all()

    return {
        "terms": [
            {
                "id": str(q.id),
                "text": q.text,
                "url": q.url,
                "click_url": q.click_url,
                "geo": q.geo,
                "daily_clicks": q.daily_clicks,
                "position": q.position,
            }
            for q in queries
        ],
        "total": len(queries),
    }


# --- Queue ------------------------------------------------------------------ #

@router.post("/queue/push")
async def push_tasks(
    body: dict,
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """Push tasks to the token's project queue (pending duplicates by click_url are skipped)."""
    project_query_ids = set(
        (await session.execute(select(Query.id).where(Query.project_id == project.id))).scalars()
    )
    queued = 0
    exists = 0

    for task_data in body.get("tasks", []):
        click_url = task_data.get("click_url")
        if not click_url:
            continue
        query_id = parse_uuid(task_data["query_id"], "query_id") if task_data.get("query_id") else None
        if query_id is not None and query_id not in project_query_ids:
            raise HTTPException(status_code=422, detail=f"query_id {query_id} doesn't belong to this project")
        source = task_data.get("source", "strategy")
        if source not in _TASK_SOURCES:
            raise HTTPException(status_code=422, detail=f"Unknown source: {source}")

        duplicate = (await session.execute(
            select(QueueTask.id).where(
                QueueTask.project_id == project.id,
                QueueTask.click_url == click_url,
                QueueTask.status == "pending",
            )
        )).first()
        if duplicate:
            exists += 1
            continue

        session.add(QueueTask(
            id=uuid4(),
            project_id=project.id,
            query_id=query_id,
            click_url=click_url,
            source=source,
            geo=task_data.get("geo", {}),
        ))
        await session.flush()  # so a repeated URL within this batch is seen as a duplicate
        queued += 1

    await session.commit()
    return {"queued": queued, "already_exists": exists}


@router.post("/queue/claim")
async def claim_tasks(
    body: dict | None = None,
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """Hand out up to ``limit`` pending tasks (oldest first) and mark them in_progress.

    Each task is handed out once; agents report back via /queue/results. Tasks left
    in_progress for 30+ minutes are marked stuck by the stale checker.
    """
    try:
        limit = min(max(int((body or {}).get("limit", 10)), 1), 100)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="limit must be an integer")
    if not project.is_active:
        return {"tasks": []}

    rows = (await session.execute(
        select(QueueTask, Query.text)
        .outerjoin(Query, Query.id == QueueTask.query_id)
        .where(QueueTask.project_id == project.id, QueueTask.status == "pending")
        .order_by(QueueTask.created_at)
        .limit(limit)
        .with_for_update(of=QueueTask, skip_locked=True)  # concurrent agents never get the same task
    )).all()
    for task, _ in rows:
        task.status = "in_progress"
    await session.commit()
    return {"tasks": [_task_json(task, text) for task, text in rows]}


@router.get("/queue")
async def list_queue(
    status: str = "",
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """List queue tasks of the token's project (read-only; use /queue/claim to take tasks)."""
    query = (
        select(QueueTask, Query.text)
        .outerjoin(Query, Query.id == QueueTask.query_id)
        .where(QueueTask.project_id == project.id)
    )
    if status:
        if status not in _TASK_STATUSES:
            raise HTTPException(status_code=422, detail=f"Unknown status: {status}")
        query = query.where(QueueTask.status == status)

    rows = (await session.execute(query.order_by(QueueTask.created_at))).all()
    return {"tasks": [_task_json(task, text) for task, text in rows], "total": len(rows)}


@router.post("/queue/clear")
async def clear_queue(
    project_id: str = "",
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """Delete pending and in-progress tasks of the token's project."""
    _ensure_same_project(project, project_id)
    result = await session.execute(
        delete(QueueTask).where(
            QueueTask.project_id == project.id,
            QueueTask.status.in_(["pending", "in_progress"]),
        )
    )
    await session.commit()
    return {"deleted": result.rowcount}


@router.post("/queue/results")
async def submit_results(
    body: dict,
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """Submit interaction results from agents."""
    updated = 0
    errors = []
    for r in body.get("results", []):
        task_id = r.get("task_id")
        new_status = r.get("status")
        if not task_id or not new_status:
            errors.append({"task_id": task_id, "error": "task_id and status are required"})
            continue
        if new_status not in _TASK_STATUSES:
            raise HTTPException(status_code=422, detail=f"Unknown status: {new_status}")

        task = await session.get(QueueTask, parse_uuid(task_id, "task_id"))
        if task and task.project_id == project.id:  # type: ignore[attr-defined]
            task.status = new_status  # type: ignore[attr-defined]
            if "position" in r:
                task.position = r["position"]  # type: ignore[attr-defined]
            if "details" in r:
                task.details = r["details"]  # type: ignore[attr-defined]
            updated += 1
        else:
            errors.append({"task_id": task_id, "error": "not found"})

    await session.commit()
    return {"updated": updated, "errors": errors}


# --- Users ------------------------------------------------------------------ #
# There is no organization model yet, so these operations can't do anything real.
# They answer 501 instead of pretending to succeed.

_NO_ORGANIZATIONS = "Organization users are not implemented yet"


@router.post("/users", status_code=501)
async def create_user(project = Depends(_get_project_by_token)):  # type: ignore[assignment]
    """Invite a user to the organization (not implemented)."""
    raise HTTPException(status_code=501, detail=_NO_ORGANIZATIONS)


@router.get("/users", status_code=501)
async def list_users(project = Depends(_get_project_by_token)):  # type: ignore[assignment]
    """List organization users (not implemented)."""
    raise HTTPException(status_code=501, detail=_NO_ORGANIZATIONS)


@router.put("/users/{user_id}", status_code=501)
async def update_user(user_id: str, project = Depends(_get_project_by_token)):  # type: ignore[assignment]
    """Update a user in the organization (not implemented)."""
    raise HTTPException(status_code=501, detail=_NO_ORGANIZATIONS)


@router.patch("/users/{user_id}/status", status_code=501)
async def update_user_status(user_id: str, project = Depends(_get_project_by_token)):  # type: ignore[assignment]
    """Toggle user active status (not implemented)."""
    raise HTTPException(status_code=501, detail=_NO_ORGANIZATIONS)


# --- Balance ---------------------------------------------------------------- #

@router.post("/balance/add")
async def add_project_balance(
    body: dict,
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """Add credits (rubles) to the token's project."""
    txn = await add_balance(session, project, body.get("amount", 0), body.get("description", "External API"))
    return {**balance_payload(project), "added": txn.amount / 100}


@router.post("/balance/set")
async def set_project_balance(
    body: dict,
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """Set the token's project balance (rubles)."""
    await set_balance(session, project, body.get("balance", 0), body.get("description", "External API"))
    return balance_payload(project)


# --- Boosts & Groups -------------------------------------------------------- #

@router.get("/boosts")
async def list_boosts(
    project_id: str = "",
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """List boosts (queries with a boost range) of the token's project."""
    _ensure_same_project(project, project_id)
    queries = (await session.execute(
        select(Query).where(Query.project_id == project.id, Query.boost_min.isnot(None), Query.boost_max.isnot(None))
    )).scalars().all()

    boosts = [
        {
            "id": str(q.id),
            "query_text": q.text,
            "boost_min": q.boost_min,
            "boost_max": q.boost_max,
            "frequency": q.frequency,
        }
        for q in queries
    ]
    return {"boosts": boosts, "total": len(boosts)}


@router.post("/boosts")
async def create_boost(
    body: dict,
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """Create or update a boost for a query (matched by text; created if missing)."""
    query_text = (body.get("query_text") or "").strip()
    if not query_text:
        raise HTTPException(status_code=422, detail="Required field(s): query_text")
    ensure_safe_url(body.get("url"), "url")
    ensure_safe_url(body.get("click_url"), "click_url")

    query = (await session.execute(
        select(Query).where(Query.project_id == project.id, Query.text == query_text)
    )).scalar_one_or_none()
    if not query:
        query = Query(
            project_id=project.id,
            text=query_text,
            url=body.get("url"),
            click_url=body.get("click_url") or search_click_url(query_text),
        )
        session.add(query)
        await session.flush()

    query.boost_min = body.get("boost_min", 5)  # type: ignore[attr-defined]
    query.boost_max = body.get("boost_max", 10)  # type: ignore[attr-defined]
    query.frequency = body.get("frequency", query.frequency)  # type: ignore[attr-defined]

    await session.commit()
    return {
        "id": str(query.id),
        "query_text": query.text,
        "boost_min": query.boost_min,  # type: ignore[attr-defined]
        "boost_max": query.boost_max,  # type: ignore[attr-defined]
    }


@router.get("/project-groups")
async def list_project_groups(
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """List project groups for the token (the token's project acts as its only group)."""
    query_count = (await session.execute(
        select(func.count()).select_from(Query).where(Query.project_id == project.id)
    )).scalar() or 0
    return {
        "groups": [{
            "id": str(project.id),
            "name": project.name,
            "domain": project.domain,
            "query_count": query_count,
        }],
        "total": 1,
    }


@router.get("/external/status")
async def external_status(
    x_auth_token: str = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    """Get external API status and, for a valid token, its project's queue stats."""
    if not x_auth_token:
        return {"status": "ok", "project": None}

    token_record = (await session.execute(
        select(ProjectToken).where(ProjectToken.token_string == x_auth_token)
    )).scalar_one_or_none()
    project = await session.get(Project, token_record.project_id) if token_record and token_record.project_id else None
    if not project:
        return {"status": "ok", "project": None}

    stats = {
        str(status): count
        for status, count in (await session.execute(
            select(QueueTask.status, func.count()).where(QueueTask.project_id == project.id).group_by(QueueTask.status)
        )).all()
    }
    return {
        "status": "ok",
        "project": {
            "id": str(project.id),
            "name": project.name,
            "domain": project.domain,
            "queue_stats": {
                "pending": stats.get("pending", 0),
                "in_progress": stats.get("in_progress", 0),
                "completed": stats.get("completed", 0),
            },
        },
    }
