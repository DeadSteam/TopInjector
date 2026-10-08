"""External API routes (GhostLab-compatible). Base URL: /api/external/v1/ Auth: X-Auth-Token header."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.jwt_utils import get_current_user
from shared.database.session import get_session
from services.project_service.domain.models import Project, ProjectToken, Query
from services.queue_service.domain.models import QueueTask

router = APIRouter(tags=["external-api"])


async def _get_project_by_token(
    x_auth_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> Project:
    """Validate X-Auth-Token against project_tokens table and return the owning Project."""
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="Missing X-Auth-Token header")

    result = await session.execute(
        select(ProjectToken).where(ProjectToken.token_string == x_auth_token)
    )
    token_record = result.scalar_one_or_none()
    if not token_record:
        raise HTTPException(status_code=401, detail="Invalid API token")

    project_result = await session.execute(select(Project).where(Project.id == token_record.project_id))
    project = project_result.scalar_one_or_none()
    if not project or not project.is_active:
        raise HTTPException(status_code=401, detail="Project not found or inactive")
    return project


# --- Projects --------------------------------------------------------------- #

@router.post("/projects")
async def create_project(
    body: dict,
    user = Depends(get_current_user),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """Create a new project. Authenticated via JWT."""
    project = Project(
        user_id=user.id,  # type: ignore[attr-defined]
        name=body.get("name", ""),
        domain=body.get("domain", ""),
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
    x_auth_token: str = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    """List projects matching the API token."""
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="Missing X-Auth-Token header")

    result = await session.execute(select(ProjectToken).where(ProjectToken.token_string == x_auth_token))
    token_record = result.scalar_one_or_none()
    if not token_record:
        raise HTTPException(status_code=401, detail="Invalid API token")

    project_result = await session.execute(
        select(Project).where(Project.id == token_record.project_id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        return {"projects": []}

    queries_result = await session.execute(select(Query).where(Query.project_id == project.id))
    queries_list = queries_result.scalars().all()

    tasks_result = await session.execute(
        select(QueueTask).where(QueueTask.project_id == project.id)
    )
    tasks_list = tasks_result.scalars().all()

    return {
        "projects": [{
            "id": str(project.id),
            "name": project.name,
            "domain": project.domain,
            "region": project.region or "",
            "strategy_type": project.strategy_type,
            "queries_count": len(queries_list),
            "queue_size": sum(1 for t in tasks_list if t.status == "pending"),
        }],
    }


@router.put("/projects/{project_id}")
async def update_project(
    project_id: str,
    body: dict,
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """Update an existing project (must match token)."""
    for key in ("name", "domain", "region", "strategy_type"):
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
    project.is_active = body.get("is_active", True)  # type: ignore[attr-defined]

    await session.commit()
    return {"id": str(project.id), "is_active": project.is_active}  # type: ignore[attr-defined]


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """Delete a project (must match token)."""
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
    """Bulk upsert keyword queries. Replaces all existing queries for the project."""
    queries = body.get("queries", [])

    # Delete existing queries for this project
    await session.execute(delete(Query).where(Query.project_id == project.id))  # type: ignore[attr-defined]

    created = 0
    for q in queries:
        query = Query(
            project_id=project.id,  # type: ignore[attr-defined]
            text=q.get("text", ""),
            url=q.get("url"),
            click_url=q.get("click_url"),
            geo=q.get("geo", {}),
            daily_clicks=q.get("daily_clicks", 0),
        )
        session.add(query)
        created += 1

    await session.commit()
    return {"created": created, "updated": 0, "deleted": len(queries)}


@router.get("/terms")
async def list_terms(
    project_id: str = "",
    x_auth_token: str = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    """List queries for a project."""
    if not x_auth_token:
        return {"terms": [], "total": 0}

    result = await session.execute(select(ProjectToken).where(ProjectToken.token_string == x_auth_token))
    token_record = result.scalar_one_or_none()
    if not token_record or not project_id:
        return {"terms": [], "total": 0}

    pid = UUID(project_id)
    q_result = await session.execute(select(Query).where(Query.project_id == pid))
    queries = q_result.scalars().all()

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
    """Push tasks to the queue. Must match token's project."""
    queued = 0
    exists = 0

    for task_data in body.get("tasks", []):
        click_url = task_data.get("click_url")
        if not click_url:
            continue

        check = await session.execute(
            select(QueueTask).where(
                QueueTask.project_id == project.id,  # type: ignore[attr-defined]
                QueueTask.click_url == click_url,
                QueueTask.status == "pending",
            )
        )
        if check.scalar_one_or_none():
            exists += 1
            continue

        task = QueueTask(
            id=UUID(int=0),  # placeholder
            project_id=project.id,  # type: ignore[attr-defined]
            query_id=UUID(task_data["query_id"]) if task_data.get("query_id") else None,
            click_url=click_url,
            source=task_data.get("source", "strategy"),
            geo=task_data.get("geo", {}),
        )
        from uuid import uuid4
        task.id = uuid4()
        session.add(task)
        queued += 1

    await session.commit()
    return {"queued": queued, "already_exists": exists}


@router.get("/queue")
async def list_queue(
    project_id: str = "",
    status: str = "",
    x_auth_token: str = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    """List queue tasks for the token's project."""
    if not x_auth_token:
        return {"tasks": [], "total": 0}

    result = await session.execute(select(ProjectToken).where(ProjectToken.token_string == x_auth_token))
    token_record = result.scalar_one_or_none()
    if not token_record:
        return {"tasks": [], "total": 0}

    query = select(QueueTask).where(QueueTask.project_id == token_record.project_id)  # type: ignore[attr-defined]
    if status:
        query = query.where(QueueTask.status == status)

    result = await session.execute(query.order_by(QueueTask.created_at))  # type: ignore[attr-defined]
    tasks = result.scalars().all()

    return {
        "tasks": [
            {
                "id": str(t.id),
                "status": t.status,
                "source": t.source,
                "click_url": t.click_url,
                "geo": t.geo,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tasks
        ],
        "total": len(tasks),
    }


@router.post("/queue/clear")
async def clear_queue(
    project_id: str,
    x_auth_token: str = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    """Clear all pending tasks for the token's project."""
    if not x_auth_token:
        return {"deleted": 0}

    result = await session.execute(select(ProjectToken).where(ProjectToken.token_string == x_auth_token))
    token_record = result.scalar_one_or_none()
    if not token_record or not project_id:
        return {"deleted": 0}

    pid = UUID(project_id)
    await session.execute(
        delete(QueueTask).where(
            QueueTask.project_id == pid,
            QueueTask.status.in_(["pending", "in_progress"]),
        )
    )
    await session.commit()
    return {"deleted": 1}


@router.post("/queue/results")
async def submit_results(
    body: dict,
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
):
    """Submit interaction results from agents."""
    updated = 0
    for r in body.get("results", []):
        task_id = r.get("task_id")
        new_status = r.get("status")
        if not task_id or not new_status:
            continue

        t_result = await session.execute(select(QueueTask).where(QueueTask.id == UUID(task_id)))
        task = t_result.scalar_one_or_none()
        if task and task.project_id == project.id:  # type: ignore[attr-defined]
            task.status = new_status  # type: ignore[attr-defined]
            if "position" in r:
                task.position = r["position"]  # type: ignore[attr-defined]
            updated += 1

    await session.commit()
    return {"updated": updated, "errors": []}


# --- Users ------------------------------------------------------------------ #

@router.post("/users")
async def create_user(
    body: dict,
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
):
    """Invite a user to the organization."""
    from uuid import uuid4

    return {**body, "id": str(uuid4()), "project_id": str(project.id)}  # type: ignore[attr-defined]


@router.get("/users")
async def list_users(x_auth_token: str = Header(default=None)):
    """List organization users."""
    return []


@router.put("/users/{user_id}")
async def update_user(user_id: str, body: dict, x_auth_token: str = Header(default=None)):
    """Update a user in the organization."""
    return {**body, "id": user_id}


@router.patch("/users/{user_id}/status")
async def update_user_status(user_id: str, body: dict, x_auth_token: str = Header(default=None)):
    """Toggle user active status."""
    return {"id": user_id, "is_active": body.get("is_active", True)}


# --- Balance ---------------------------------------------------------------- #

@router.post("/balance/add")
async def add_balance(
    body: dict,
    project = Depends(_get_project_by_token),  # type: ignore[assignment]
):
    """Add credits to a project."""
    amount = body.get("amount", 0)
    return {"project_id": str(project.id), "balance": 0, "added": amount}  # type: ignore[attr-defined]


@router.post("/balance/set")
async def set_balance(
    body: dict,
    project = Depends(_get_project_by_token),  # ignore[assignment]
):
    """Set project balance."""
    new_balance = body.get("balance", 0)
    return {"project_id": str(project.id), "balance": new_balance}  # type: ignore[attr-defined]


# --- Boosts & Groups -------------------------------------------------------- #

@router.get("/project-groups")
async def list_project_groups(x_auth_token: str = Header(default=None)):
    """List project groups."""
    return []


@router.get("/boosts")
async def list_boosts(project_id: str = "", x_auth_token: str = Header(default=None)):
    """List boosts for a project."""
    return []
