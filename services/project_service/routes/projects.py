"""Project service routes — CRUD for projects, queries, groups and more."""

from uuid import UUID, uuid4
import csv as _csv
import io as _io
import json as _json

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy import func, select, case as sa_case, text as sa_text, cast as sa_cast
from sqlalchemy.types import Date as sa_Date
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.session import get_session
from services.project_service.domain.models import (
    Project,
    ProjectToken,
    Query as _QueryModel,
    Marker,
    Webmarker,
    ProjectGroup,
    ProjectDelegate,
)
from services.project_service.repositories.project_repo import ProjectRepository
from services.project_service.repositories.query_repo import QueryRepository
from services.queue_service.domain.models import QueueTask
from services.queue_service.repositories.task_repo import QueueTaskRepository

router = APIRouter(tags=["projects"])


# --- helpers --------------------------------------------------------------- #

async def _project_repo(
    session: AsyncSession = Depends(get_session),
) -> ProjectRepository:
    return ProjectRepository(session)


async def _query_repo(
    session: AsyncSession = Depends(get_session),
) -> QueryRepository:
    return QueryRepository(session)


async def _task_repo(
    session: AsyncSession = Depends(get_session),
) -> QueueTaskRepository:
    return QueueTaskRepository(session)


# --------------------------------------------------------------------------- #
#  Project Groups                                                             #
# --------------------------------------------------------------------------- #

@router.get("/groups")
async def list_groups(
    session: AsyncSession = Depends(get_session),
):
    """List all groups for the current user."""
    result = await session.execute(select(ProjectGroup))
    groups = result.scalars().all()
    return [
        {
            "id": str(g.id),
            "name": g.name,
            "icon": g.icon or "",
        }
        for g in groups
    ]


@router.post("/groups")
async def create_group(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Create a new project group."""
    group = ProjectGroup(
        id=uuid4(),
        name=body["name"],
        icon=body.get("icon", ""),
    )
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return {"id": str(group.id), "name": group.name, "icon": group.icon}


@router.put("/groups/{group_id}")
async def update_group(
    group_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Update a project group."""
    result = await session.execute(select(ProjectGroup).where(ProjectGroup.id == UUID(group_id)))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    for key in ("name", "icon"):
        if key in body:
            setattr(group, key, body[key])
    await session.commit()
    await session.refresh(group)
    return {"id": str(group.id), "name": group.name, "icon": group.icon}


@router.delete("/groups/{group_id}")
async def delete_group(
    group_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete a project group (un-assigns projects from it)."""
    result = await session.execute(select(ProjectGroup).where(ProjectGroup.id == UUID(group_id)))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    # Un-assign all projects
    await session.execute(
        select(Project).where(Project.group_id == UUID(group_id))
    )
    projects_result = (await session.execute(
        select(Project).where(Project.group_id == UUID(group_id))
    )).scalars().all()
    for p in projects_result:
        p.group_id = None  # type: ignore[attr-defined]
    await session.delete(group)
    await session.commit()
    return {"deleted": True}


# --------------------------------------------------------------------------- #
#  Projects                                                                   #
# --------------------------------------------------------------------------- #

@router.post("/")
async def create_project(
    body: dict,
    project_repo: ProjectRepository = Depends(_project_repo),
):
    """Create a new project."""
    user_id_raw = body.get("user_id")
    if user_id_raw:
        try:
            user_id = UUID(user_id_raw)  # type: ignore[assignment]
        except ValueError:
            user_id = uuid4()
    else:
        user_id = uuid4()

    group_id: UUID | None = None
    gid = body.get("group_id")
    if gid:
        try:
            group_id = UUID(gid)  # type: ignore[assignment]
        except ValueError:
            pass

    project = Project(
        id=uuid4(),
        user_id=user_id,
        name=body["name"],
        domain=body["domain"],
        strategy_type=body.get("strategy_type", "daily"),
        daily_limit=body.get("daily_limit", 500),
        region=body.get("region"),
        group_id=group_id,
    )
    project = await project_repo.create(project)
    return {"id": str(project.id), "name": project.name, "domain": project.domain}


@router.get("/")
async def list_projects(
    search: str | None = Query(default=None),
    group_id: str | None = Query(default=None),
    region: str | None = Query(default=None),
    strategy_type: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    project_repo: ProjectRepository = Depends(_project_repo),
    session: AsyncSession = Depends(get_session),
):
    """List projects with optional filters and search."""

    stmt = select(Project)

    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(Project.name.ilike(pattern))
    if group_id:
        stmt = stmt.where(Project.group_id == UUID(group_id))
    if region:
        stmt = stmt.where(Project.region == region)
    if strategy_type:
        stmt = stmt.where(Project.strategy_type == strategy_type)
    if is_active is not None:
        stmt = stmt.where(Project.is_active == is_active)

    result = await session.execute(stmt.order_by(Project.name))
    projects = result.scalars().all()

    # Also fetch query counts and queue stats per project
    proj_uuids = [p.id for p in projects]
    counts_map: dict[str, int] = {}
    if proj_uuids:
        q_result = await session.execute(
            select(_QueryModel.project_id, func.count())
            .where(_QueryModel.project_id.in_(proj_uuids))  # type: ignore[arg-type]
            .group_by(_QueryModel.project_id)
        )
        counts_map = {str(r[0]): r[1] for r in q_result.all()}

    # Check delegation: build set of project IDs the current user is a delegate for
    delegated_ids: set[str] = set()
    if proj_uuids:
        del_result = await session.execute(
            select(ProjectDelegate.project_id)
            .where(ProjectDelegate.project_id.in_(proj_uuids))  # type: ignore[arg-type]
        )
        delegated_ids = {str(r[0]) for r in del_result.all()}

    return [
        {
            "id": str(p.id),
            "name": p.name,
            "domain": p.domain,
            "region": p.region or "",
            "strategy_type": p.strategy_type,
            "daily_limit": p.daily_limit,
            "is_active": p.is_active,
            "group_id": str(p.group_id) if p.group_id else None,  # type: ignore[attr-defined]
            "group_name": p.group.name if p.group else None,  # type: ignore[attr-defined]
            "query_count": counts_map.get(str(p.id), 0),
            "is_delegate": str(p.id) in delegated_ids,
        }
        for p in projects
    ]


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    project_repo: ProjectRepository = Depends(_project_repo),
):
    """Get a single project by ID."""
    project = await project_repo.get_by_id(UUID(project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "id": str(project.id),
        "name": project.name,
        "domain": project.domain,
        "strategy_type": project.strategy_type,
        "daily_limit": project.daily_limit,
        "region": project.region,
        "is_active": project.is_active,
        "group_id": str(project.group_id) if project.group_id else None,  # type: ignore[attr-defined]
        "group_name": project.group.name if project.group else None,  # type: ignore[attr-defined]
        "geo_settings": project.geo_settings or {},
        "integrations": project.integrations or {},
    }


@router.put("/{project_id}")
async def update_project(
    project_id: str,
    body: dict,
    project_repo: ProjectRepository = Depends(_project_repo),
):
    """Update an existing project."""
    project = await project_repo.get_by_id(UUID(project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for key, value in body.items():
        if hasattr(project, key) and key not in ("id", "created_at", "updated_at"):
            setattr(project, key, value)
    return {"id": str(project.id), "updated": True}


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    project_repo: ProjectRepository = Depends(_project_repo),
):
    """Delete a project."""
    project = await project_repo.get_by_id(UUID(project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await project_repo.delete(project)
    return {"deleted": True}


# --- Query endpoints -------------------------------------------------------- #

@router.post("/{project_id}/queries")
async def add_query(
    project_id: str,
    body: dict,
    query_repo: QueryRepository = Depends(_query_repo),
):
    """Add a query (term) to a project."""
    text = body["text"]

    # Generate search click URL if not provided
    if not body.get("click_url"):
        import urllib.parse as _urllib

        engine = body.get("search_engine", "google")
        params = {"q": text}
        encoded = _urllib.urlencode(params)
        engines_map: dict[str, str] = {
            "google": f"https://www.google.com/search?{encoded}",
            "yandex": f"https://yandex.ru/search/?text={_urllib.quote(text)}",
            "bing": f"https://www.bing.com/search?q={encoded}",
        }
        click_url = engines_map.get(engine, engines_map["google"])
    else:
        click_url = body["click_url"]

    query = _QueryModel(
        project_id=UUID(project_id),
        text=text,
        url=body.get("url"),
        click_url=click_url,
        geo=body.get("geo", {}),
    )
    query = await query_repo.create(query)
    return {
        "id": str(query.id),
        "text": query.text,
        "url": query.url,
        "click_url": query.click_url,
    }


@router.get("/{project_id}/queries")
async def list_queries(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    query_repo: QueryRepository = Depends(_query_repo),
    task_repo: QueueTaskRepository = Depends(_task_repo),
):
    """List all queries for a project with completed counts."""
    queries = await query_repo.get_by_project(UUID(project_id))

    # Get completed count per query
    result = await session.execute(
        select(QueueTask.query_id, func.count())
        .where(
            QueueTask.project_id == UUID(project_id),
            QueueTask.status == "completed",
            QueueTask.query_id.isnot(None),
        )
        .group_by(QueueTask.query_id)
    )
    completed_map: dict[str, int] = {str(r[0]): r[1] for r in result.all()}

    return [
        {
            "id": str(q.id),
            "text": q.text,
            "url": q.url,
            "click_url": q.click_url,
            "geo": q.geo,
            "daily_clicks": q.daily_clicks,
            "position": q.position,
            "completed": completed_map.get(str(q.id), 0),
        }
        for q in queries
    ]


@router.put("/{project_id}/queries/{query_id}")
async def update_query(
    project_id: str,
    query_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Update a single query (inline editing: geo, daily_clicks, click_url, url)."""
    result = await session.execute(select(_QueryModel).where(_QueryModel.id == UUID(query_id)))
    query = result.scalar_one_or_none()
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")
    # Only allowed fields
    allowed_fields = ("geo", "daily_clicks", "click_url", "url", "position", "frequency")
    for key in allowed_fields:
        if key in body and hasattr(query, key):
            setattr(query, key, body[key])
    await session.commit()
    await session.refresh(query)
    return {
        "id": str(query.id),
        "text": query.text,
        "url": query.url,
        "click_url": query.click_url,
        "geo": query.geo,
        "daily_clicks": query.daily_clicks,
        "frequency": query.frequency,
    }


@router.delete("/{project_id}/queries/{query_id}")
async def delete_query(
    project_id: str,
    query_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete a query from a project."""
    result = await session.execute(select(_QueryModel).where(_QueryModel.id == UUID(query_id)))
    query = result.scalar_one_or_none()
    if not query or query.project_id != UUID(project_id):
        raise HTTPException(status_code=404, detail="Query not found")
    await session.delete(query)
    await session.commit()
    return {"deleted": True}


@router.post("/{project_id}/boost")
async def boost_queries(
    project_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Boost selected queries: update daily_clicks/frequency/click_url and regenerate queue tasks."""
    query_ids: list[str] = body.get("query_ids", [])
    if not query_ids:
        raise HTTPException(status_code=400, detail="No query IDs provided")

    new_daily_clicks = max(1, int(body.get("daily_clicks", 0)))
    interval_seconds = int(body.get("interval_seconds", 3600))
    start_from_now = body.get("start_from_now", True)
    new_click_url = body.get("click_url") or ""

    from datetime import datetime, timezone, timedelta
    from sqlalchemy import update as sa_update

    for qid in query_ids:
        # Update query fields
        result = await session.execute(select(_QueryModel).where(_QueryModel.id == UUID(qid)))
        query = result.scalar_one_or_none()
        if not query or query.project_id != UUID(project_id):
            continue
        query.daily_clicks = new_daily_clicks  # type: ignore[attr-defined]
        query.frequency = max(1, int(body.get("frequency", query.frequency)))  # type: ignore[attr-defined]
        if new_click_url:
            query.click_url = new_click_url  # type: ignore[attr-defined]

    # Clear pending/in_progress strategy tasks for this project to regenerate
    await session.execute(
        sa_update(QueueTask)
        .where(
            QueueTask.project_id == UUID(project_id),
            QueueTask.status.in_(["pending", "in_progress"]),  # type: ignore[arg-type]
            QueueTask.source == "strategy",
        )
        .values(status="pending")
    )

    await session.commit()

    return {
        "boosted": len(query_ids),
        "daily_clicks": new_daily_clicks,
        "interval_seconds": interval_seconds,
    }


# --- Request table for position tracking -------------------------------------- #


@router.get("/{project_id}/request-table")
async def get_request_table(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Return detailed per-query stats: frequency, avg_position, clicks_today, autoburst."""
    from datetime import date, timedelta

    today = date.today().isoformat()

    result = await session.execute(
        select(
            _QueryModel.id,
            _QueryModel.text,
            _QueryModel.frequency,
            _QueryModel.daily_clicks,
            _QueryModel.click_url,
            func.avg(QueueTask.position).label("avg_position"),
            func.count(
                QueueTask.id
            ).label("total_tasks"),
            func.sum(
                sa_case((QueueTask.status == "completed", 1), else_=0)
            ).label("completed_count"),
        )
        .join(QueueTask, _QueryModel.id == QueueTask.query_id, isouter=True)
        .where(_QueryModel.project_id == UUID(project_id))
        .group_by(_QueryModel.id, _QueryModel.text, _QueryModel.frequency, _QueryModel.daily_clicks, _QueryModel.click_url)
    )

    rows = []
    for r in result.all():
        avg_pos = r.avg_position
        rows.append({
            "id": str(r[0]),
            "text": r[1],
            "frequency": r[2] or 1,
            "daily_clicks": r[3] or 0,
            "avg_position": round(float(avg_pos), 1) if avg_pos else None,
            "total_tasks": r.total_tasks or 0,
            "completed_count": r.completed_count or 0,
        })

    return {"project_id": project_id, "queries": rows}


# --- Queue stats & positions ------------------------------------------------ #

@router.get("/{project_id}/queue-stats")
async def get_queue_stats(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Return queue task counts by status for a project."""
    result = await session.execute(
        select(QueueTask.status, func.count())
        .where(QueueTask.project_id == UUID(project_id))
        .group_by(QueueTask.status)
    )
    stats: dict[str, int] = {str(r[0]): r[1] for r in result.all()}
    return {
        "pending": stats.get("pending", 0),
        "in_progress": stats.get("in_progress", 0),
        "completed": stats.get("completed", 0),
        "not_found": stats.get("not_found", 0),
        "stuck": stats.get("stuck", 0),
    }


@router.get("/{project_id}/positions")
async def get_positions(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Return position history for queries in a project."""
    result = await session.execute(
        select(_QueryModel.text, QueueTask.position)
        .join(QueueTask, _QueryModel.id == QueueTask.query_id)
        .where(
            _QueryModel.project_id == UUID(project_id),
            QueueTask.status == "completed",
            QueueTask.position.isnot(None),
        )
        .order_by(QueueTask.created_at)
    )
    history = [{"text": r[0], "position": r[1], "date": ""} for r in result.all()]
    return {"project_id": project_id, "history": history}


# --- Position trend data ---------------------------------------------------- #

@router.get("/{project_id}/trend")
async def get_position_trend(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Return aggregated daily position averages per query for trend chart."""
    from datetime import date

    result = await session.execute(
        select(
            _QueryModel.text,
            QueueTask.position,
            func.date(QueueTask.created_at).label("day"),
        )
        .join(QueueTask, _QueryModel.id == QueueTask.query_id)
        .where(
            _QueryModel.project_id == UUID(project_id),
            QueueTask.status == "completed",
            QueueTask.position.isnot(None),
        )
    )

    # Aggregate into per-query daily averages
    from collections import defaultdict

    agg: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    query_texts: set[str] = set()
    for text_val, pos_val, day_val in result.all():
        if text_val is None or pos_val is None or day_val is None:
            continue
        agg[text_val][str(day_val)].append(float(pos_val))
        query_texts.add(text_val)

    # Build trend lines sorted by date
    from datetime import date as _date
    all_days: list[str] = sorted(agg.keys()) if any(agg.values()) else []
    # Actually need to collect all unique days across ALL queries
    all_day_set: set[str] = set()
    for q in agg.values():
        all_day_set.update(q.keys())
    all_days = sorted(all_day_set)

    lines: list[dict] = []
    for txt in sorted(query_texts):
        data_points: list[dict] = []
        if txt in agg:
            for day_str in all_days:
                vals = agg[txt].get(day_str, [])
                if vals:
                    avg_val = sum(vals) / len(vals)
                    data_points.append({"date": day_str, "position": round(avg_val, 2)})
        lines.append({"text": txt, "data": data_points})

    return {"project_id": project_id, "lines": lines}


# --- Markers ---------------------------------------------------------------- #

@router.get("/{project_id}/markers")
async def list_markers(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """List markers for a project."""
    result = await session.execute(
        select(Marker).where(Marker.project_id == UUID(project_id))
    )
    markers = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "name": m.name,
            "url": m.url,
            "css_selector": m.css_selector,
            "description": m.description,
            "is_active": m.is_active,
        }
        for m in markers
    ]


@router.post("/{project_id}/markers")
async def create_marker(
    project_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Create a new marker."""
    from uuid import uuid4

    marker = Marker(
        id=uuid4(),
        project_id=UUID(project_id),
        name=body.get("name", ""),
        url=body.get("url", ""),
        css_selector=body.get("css_selector"),
        description=body.get("description"),
    )
    session.add(marker)
    await session.commit()
    await session.refresh(marker)
    return {
        "id": str(marker.id),
        "name": marker.name,
        "url": marker.url,
        "css_selector": marker.css_selector,
        "description": marker.description,
        "is_active": marker.is_active,
    }


@router.put("/{project_id}/markers/{marker_id}")
async def update_marker(
    project_id: str,
    marker_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Update a marker."""
    result = await session.execute(select(Marker).where(Marker.id == UUID(marker_id)))
    marker = result.scalar_one_or_none()
    if not marker:
        raise HTTPException(status_code=404, detail="Marker not found")

    for key in ("name", "url", "css_selector", "description", "is_active"):
        if key in body:
            setattr(marker, key, body[key])

    await session.commit()
    await session.refresh(marker)
    return {
        "id": str(marker.id),
        "name": marker.name,
        "url": marker.url,
        "css_selector": marker.css_selector,
        "description": marker.description,
        "is_active": marker.is_active,
    }


@router.delete("/{project_id}/markers/{marker_id}")
async def delete_marker(
    project_id: str,
    marker_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete a marker."""
    result = await session.execute(select(Marker).where(Marker.id == UUID(marker_id)))
    marker = result.scalar_one_or_none()
    if not marker:
        raise HTTPException(status_code=404, detail="Marker not found")

    await session.delete(marker)
    await session.commit()
    return {"deleted": True}


# --- Webmarkers --------------------------------------------------------------- #

@router.get("/{project_id}/webmarkers")
async def list_webmarkers(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """List webmarkers for a project."""
    result = await session.execute(
        select(Webmarker).where(Webmarker.project_id == UUID(project_id))
    )
    wm_list = result.scalars().all()
    return [
        {
            "id": str(w.id),
            "platform": w.platform,
            "verification_code": w.verification_code,
            "is_verified": w.is_verified,
            "last_sync": w.last_sync.isoformat() if w.last_sync else None,
        }
        for w in wm_list
    ]


@router.post("/{project_id}/webmarkers")
async def create_webmarker(
    project_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Create a new webmarker."""
    from uuid import uuid4

    webmarker = Webmarker(
        id=uuid4(),
        project_id=UUID(project_id),
        platform=body.get("platform", ""),
        verification_code=body.get("verification_code"),
    )
    session.add(webmarker)
    await session.commit()
    await session.refresh(webmarker)
    return {
        "id": str(webmarker.id),
        "platform": webmarker.platform,
        "verification_code": webmarker.verification_code,
        "is_verified": webmarker.is_verified,
        "last_sync": webmarker.last_sync.isoformat() if webmarker.last_sync else None,
    }


@router.put("/{project_id}/webmarkers/{webmarker_id}")
async def update_webmarker(
    project_id: str,
    webmarker_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Update a webmarker."""
    result = await session.execute(select(Webmarker).where(Webmarker.id == UUID(webmarker_id)))
    wm = result.scalar_one_or_none()
    if not wm:
        raise HTTPException(status_code=404, detail="Webmarker not found")

    for key in ("platform", "verification_code", "is_verified"):
        if key in body:
            setattr(wm, key, body[key])

    await session.commit()
    await session.refresh(wm)
    return {
        "id": str(wm.id),
        "platform": wm.platform,
        "verification_code": wm.verification_code,
        "is_verified": wm.is_verified,
        "last_sync": wm.last_sync.isoformat() if wm.last_sync else None,
    }


@router.post("/{project_id}/webmarkers/{webmarker_id}/verify")
async def verify_webmarker(
    project_id: str,
    webmarker_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Mark a webmarker as verified."""
    result = await session.execute(select(Webmarker).where(Webmarker.id == UUID(webmarker_id)))
    wm = result.scalar_one_or_none()
    if not wm:
        raise HTTPException(status_code=404, detail="Webmarker not found")

    wm.is_verified = True  # type: ignore[attr-defined]
    from datetime import datetime, timezone
    wm.last_sync = datetime.now(timezone.utc)
    await session.commit()
    return {
        "id": str(wm.id),
        "is_verified": wm.is_verified,  # type: ignore[attr-defined]
        "last_sync": wm.last_sync.isoformat() if wm.last_sync else None,
    }


@router.delete("/{project_id}/webmarkers/{webmarker_id}")
async def delete_webmarker(
    project_id: str,
    webmarker_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete a webmarker."""
    result = await session.execute(select(Webmarker).where(Webmarker.id == UUID(webmarker_id)))
    wm = result.scalar_one_or_none()
    if not wm:
        raise HTTPException(status_code=404, detail="Webmarker not found")

    await session.delete(wm)
    await session.commit()
    return {"deleted": True}


# --- Project Delegates -------------------------------------------------------- #

@router.get("/{project_id}/delegates")
async def list_delegates(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """List delegates for a project."""

    result = await session.execute(
        select(ProjectDelegate)
        .where(ProjectDelegate.project_id == UUID(project_id))
    )
    delegates = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "delegate_user_id": str(d.delegate_user_id),
            "inviter_user_id": str(d.inviter_user_id),
            "role": d.role,
        }
        for d in delegates
    ]


@router.post("/{project_id}/delegates")
async def add_delegate(
    project_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Add a delegate to a project."""
    delegate_uid = UUID(body["delegate_user_id"])
    role = body.get("role", "view")

    existing = await session.execute(
        select(ProjectDelegate)
        .where(
            ProjectDelegate.project_id == UUID(project_id),
            ProjectDelegate.delegate_user_id == delegate_uid,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User already a delegate")

    inviter_raw = body.get("inviter_user_id")
    inviter_uuid = UUID(inviter_raw) if isinstance(inviter_raw, str) else (inviter_raw or uuid4())

    invite = ProjectDelegate(
        id=uuid4(),
        project_id=UUID(project_id),
        delegate_user_id=delegate_uid,
        inviter_user_id=inviter_uuid,
        role=role,
    )
    session.add(invite)
    await session.commit()
    await session.refresh(invite)
    return {
        "id": str(invite.id),
        "delegate_user_id": str(invite.delegate_user_id),
        "role": invite.role,
    }


@router.delete("/{project_id}/delegates/{delegate_uid}")
async def remove_delegate(
    project_id: str,
    delegate_uid: str,
    session: AsyncSession = Depends(get_session),
):
    """Remove a delegate from a project."""
    result = await session.execute(
        select(ProjectDelegate)
        .where(
            ProjectDelegate.project_id == UUID(project_id),
            ProjectDelegate.delegate_user_id == UUID(delegate_uid),
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Delegate not found")

    await session.delete(invite)
    await session.commit()
    return {"deleted": True}


# --- Query Import / Export ---------------------------------------------------- #

@router.post("/{project_id}/queries/import")
async def import_queries(
    project_id: str,
    request: Request,
    query_repo: QueryRepository = Depends(_query_repo),
    session: AsyncSession = Depends(get_session),
):
    """Bulk import queries from raw CSV body."""
    csv_raw = (await request.body()).decode("utf-8")
    if not csv_raw.strip():
        raise HTTPException(status_code=400, detail="CSV content is empty")

    import csv as _csv
    import io as _io
    import urllib.parse as _urllib

    reader = _csv.DictReader(_io.StringIO(csv_raw))
    created = 0
    skipped = 0
    project_uuid = UUID(project_id)

    for row in reader:
        text = (row.get("text") or row.get("Текст") or "").strip()
        if not text:
            # Try first column as text
            first_val = next(iter(row.values()), "").strip() if row else ""
            if not first_val:
                skipped += 1
                continue
            text = first_val

        url = (row.get("url") or "").strip() or None
        click_url = ""
        if url and url.startswith(("http://", "https://")):
            # Generate yandex search click_url as default
            params = _urllib.urlencode({"q": text})
            click_url = f"https://yandex.ru/search/?text={_urllib.quote(text)}"

        query = _QueryModel(
            project_id=project_uuid,
            text=text,
            url=url if url else None,
            click_url=click_url or None,
            geo={},
            daily_clicks=0,
            position=None,
            frequency=1,
        )
        session.add(query)
        created += 1

    try:
        await session.flush()
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=422, detail=f"Import error: {str(e)}")

    return {"created": created, "skipped": skipped}


@router.get("/{project_id}/queries/export.csv")
async def export_queries(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Export all queries for a project as CSV."""
    queries_result = await session.execute(select(_QueryModel).where(_QueryModel.project_id == UUID(project_id)))
    queries = queries_result.scalars().all()

    if not queries:
        raise HTTPException(status_code=404, detail="No queries to export")

    output = _io.StringIO()
    writer = _csv.writer(output)
    writer.writerow(["text", "url", "daily_clicks", "frequency", "geo"])
    for q in queries:
        geo_str = _json.dumps(q.geo) if isinstance(q.geo, dict) else ""
        writer.writerow([q.text, q.url or "", q.daily_clicks, q.frequency, geo_str])

    from fastapi.responses import Response as FastAPIResponse

    return FastAPIResponse(
        content=output.getvalue(),
        headers={"Content-Disposition": f"attachment; filename={project_id}_queries.csv"},
        media_type="text/csv",
    )
