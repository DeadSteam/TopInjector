"""Project service routes — CRUD for projects, queries, groups and more."""

from uuid import UUID, uuid4
import csv as _csv
import io as _io
import json as _json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy import func, select, case as sa_case, text as sa_text, cast as sa_cast, and_, or_
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
    BalanceTransaction,
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


async def _get_project_or_404(
    project_id: str,
    project_repo: ProjectRepository = Depends(_project_repo),
):
    project = await project_repo.get_by_id(UUID(project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


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
        geo_settings=body.get("geo_settings", {}),
        integrations=body.get("integrations", {}),
        scheduling_window=body.get("scheduling_window"),
        query_modifications=body.get("query_modifications", {}),
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
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    project_repo: ProjectRepository = Depends(_project_repo),
    session: AsyncSession = Depends(get_session),
):
    """List projects with optional filters and pagination."""

    base_stmt = select(Project)

    # Build filter conditions for counting (same as main query)
    count_conditions = []
    filter_conditions = []

    if search:
        pattern = f"%{search}%"
        count_conditions.append(Project.name.ilike(pattern))
        filter_conditions.append(Project.name.ilike(pattern))
    if group_id:
        gid = UUID(group_id)
        count_conditions.append(Project.group_id == gid)
        filter_conditions.append(Project.group_id == gid)
    if region:
        count_conditions.append(Project.region == region)
        filter_conditions.append(Project.region == region)
    if strategy_type:
        count_conditions.append(Project.strategy_type == strategy_type)
        filter_conditions.append(Project.strategy_type == strategy_type)
    if is_active is not None:
        count_conditions.append(Project.is_active == is_active)
        filter_conditions.append(Project.is_active == is_active)

    # Count total matching projects
    count_stmt = select(func.count()).select_from(Project).where(*filter_conditions)
    total = (await session.execute(count_stmt)).scalar() or 0

    # Main query with pagination
    stmt = select(Project).where(*filter_conditions)
    stmt = stmt.order_by(Project.name)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(stmt)
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

    return {
        "items": [
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
            "balance_credits": getattr(p, "balance_credits", 0),
            "balance_rub": (getattr(p, "balance_credits", 0) / 100) if hasattr(p, "balance_credits") else 0,
        }
        for p in projects
    ],
    "total": total,
    "page": page,
    "page_size": page_size,
}


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
        "scheduling_window": project.scheduling_window,
        "query_modifications": project.query_modifications or {},
        "balance_credits": getattr(project, "balance_credits", 0),
        "balance_rub": (getattr(project, "balance_credits", 0) / 100) if hasattr(project, "balance_credits") else 0,
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
    allowed_fields = ("geo", "daily_clicks", "click_url", "url", "position", "frequency", "query_modifications")
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


# --- Dashboard / listing enhancements -------------------------------------- #

@router.get("/{project_id}/overdue-count")
async def get_overdue_count(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Return count of overdue tasks (pending with pending_check_at < now)."""
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(func.count(QueueTask.id))
        .where(
            and_(
                QueueTask.project_id == UUID(project_id),
                QueueTask.status == "pending",
                QueueTask.pending_check_at < now,
            )
        )
    )
    overdue = result.scalar() or 0
    return {"overdue": overdue}


@router.get("/{project_id}/source-breakdown")
async def get_source_breakdown(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Return completed task counts by source (strategy/autoburst/proklik) plus pending breakdown."""
    result = await session.execute(
        select(QueueTask.source, QueueTask.status, func.count())
        .where(QueueTask.project_id == UUID(project_id))
        .group_by(QueueTask.source, QueueTask.status)
    )
    breakdown: dict[str, dict[str, int]] = {}
    for source, status, count in result.all():
        breakdown.setdefault(str(source), {})[str(status)] = count  # type: ignore[call-overload]

    return {
        "completed_by_source": {
            src: bd.get("completed", 0) for src, bd in breakdown.items()
        },
        "pending_by_source": {
            src: bd.get("pending", 0) for src, bd in breakdown.items()
        },
    }


# --- Project actions (copy / auto-stop / clear-queue) ----------------------- #

@router.post("/{project_id}/copy")
async def copy_project(
    project_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Copy a project with all its queries and strategy tasks."""
    import shutil as _shutil
    from sqlalchemy import select as sa_select

    project = await session.get(Project, UUID(project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    new_name = body.get("name", f"{project.name} (copy)")  # type: ignore[attr-defined]
    new_project = Project(
        id=uuid4(),
        user_id=project.user_id,
        name=new_name,
        domain=project.domain,
        strategy_type=project.strategy_type,
        daily_limit=project.daily_limit,
        region=project.region,
        group_id=project.group_id,
        geo_settings=project.geo_settings or {},
        integrations=project.integrations or {},
        scheduling_window=project.scheduling_window,
        query_modifications=project.query_modifications or {},
    )
    session.add(new_project)
    await session.flush()  # assign ID

    # Copy queries
    queries_result = await session.execute(
        sa_select(_QueryModel).where(_QueryModel.project_id == UUID(project_id))
    )
    old_queries = queries_result.scalars().all()
    for q in old_queries:
        new_q = _QueryModel(
            id=uuid4(),
            project_id=new_project.id,  # type: ignore[attr-defined]
            text=q.text,
            url=q.url,
            click_url=q.click_url or "",
            geo=q.geo or {},
            daily_clicks=q.daily_clicks,
            position=q.position,
            frequency=q.frequency or 1,
            query_modifications=q.query_modifications or {},
        )
        session.add(new_q)

    # Copy strategy tasks (reset status to pending)
    tasks_result = await session.execute(
        sa_select(QueueTask).where(
            QueueTask.project_id == UUID(project_id),
            QueueTask.source == "strategy",
        )
    )
    old_tasks = tasks_result.scalars().all()
    for t in old_tasks:
        new_t = QueueTask(
            id=uuid4(),
            project_id=new_project.id,  # type: ignore[attr-defined]
            query_id=t.query_id,
            url=t.url or "",
            status="pending",
            source="strategy",
            created_at=t.created_at,
        )
        session.add(new_t)

    await session.commit()
    return {"id": str(new_project.id), "name": new_name}


@router.post("/{project_id}/auto-stop")
async def auto_stop_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Mark project as inactive — stops strategy scheduling."""
    project = await session.get(Project, UUID(project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.is_active = False  # type: ignore[attr-defined]
    await session.commit()
    return {"stopped": True}


@router.put("/{project_id}/auto-stop")
async def set_auto_stop(
    project_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Set auto_stop_at date/time for automatic project stop."""
    project = await session.get(Project, UUID(project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    auto_stop_raw = body.get("auto_stop_at")
    if auto_stop_raw is None:
        project.auto_stop_at = None  # type: ignore[attr-defined]
    else:
        try:
            from datetime import datetime as _dt
            dt = _dt.fromisoformat(auto_stop_raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            project.auto_stop_at = dt  # type: ignore[attr-defined]
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid auto_stop_at format (ISO-8601)")

    await session.commit()
    return {
        "auto_stop_at": project.auto_stop_at.isoformat() if project.auto_stop_at else None,  # type: ignore[attr-defined]
    }


@router.get("/{project_id}/auto-stop")
async def get_auto_stop(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get current auto_stop_at value for a project."""
    project = await session.get(Project, UUID(project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "auto_stop_at": project.auto_stop_at.isoformat() if project.auto_stop_at else None,  # type: ignore[attr-defined]
    }


@router.post("/{project_id}/activate")
async def activate_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Mark project as active."""
    project = await session.get(Project, UUID(project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.is_active = True  # type: ignore[attr-defined]
    await session.commit()
    return {"activated": True}


@router.post("/{project_id}/clear-queue")
async def clear_queue(
    project_id: str,
    body: dict = {},
    session: AsyncSession = Depends(get_session),
):
    """Clear queue tasks by status filter."""
    from sqlalchemy import update as sa_update

    target_statuses = body.get("statuses", ["pending", "in_progress"])  # type: ignore[arg-type]
    await session.execute(
        sa_update(QueueTask)
        .where(
            and_(
                QueueTask.project_id == UUID(project_id),  # type: ignore[arg-type]
                QueueTask.status.in_(target_statuses),  # type: ignore[attr-defined]
            )
        )
        .values(status="pending")
    )
    await session.commit()

    # Count remaining pending tasks
    count_result = await session.execute(
        select(func.count(QueueTask.id)).where(
            and_(
                QueueTask.project_id == UUID(project_id),  # type: ignore[arg-type]
                QueueTask.status.in_(target_statuses),  # type: ignore[attr-defined]
            )
        )
    )
    remaining = count_result.scalar() or 0
    return {"cleared": True, "remaining": remaining}


# --- Click detail for daily drill-down -------------------------------------- #

@router.get("/{project_id}/clicks")
async def get_project_clicks(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    date_str: str | None = Query(default=None),
    source: str | None = Query(default=None),
    geo: str | None = Query(default=None),
    suggestion_mode: str | None = Query(default=None, alias="suggestion_mode"),
):
    """Return click events for a project with geo/source/position/suggestion breakdown."""
    from datetime import datetime as _dt

    query = select(QueueTask).where(QueueTask.project_id == UUID(project_id))

    if date_str:
        # Filter by date (YYYY-MM-DD)
        try:
            target_date = _dt.fromisoformat(date_str).date()
            next_date = target_date.__class__(target_date.year + 1, 1, 1)
        except ValueError:
            target_date = None

        if target_date:
            query = query.where(
                and_(  # type: ignore[assignment]
                    QueueTask.created_at >= _dt.combine(target_date, _dt.min.time()).replace(tzinfo=timezone.utc),
                    QueueTask.created_at < _dt.combine(next_date, _dt.min.time()).replace(tzinfo=timezone.utc),
                )
            )

    if source:
        query = query.where(QueueTask.source == source)  # type: ignore[assignment]

    if geo:
        # Client sends a search term; filter by task.geo containing it
        geo_lower = geo.lower()
        # Use JSON contains check — task.geo is JSONB/JSON dict
        from sqlalchemy import cast as _cast, String as _String
        query = query.where(QueueTask.geo.op('->>')(geo.split(':')[0] if ':' in geo else 'country') >= '')  # placeholder, fetch all and filter below

    result = await session.execute(query.order_by(QueueTask.created_at.desc().nullslast()))
    tasks_result = result.scalars().all()

    # Client-side filtering for geo substring and suggestion_mode (cannot be done purely in SQL efficiently)
    filtered_tasks = []
    for t in tasks_result:
        # Geo filter — check if any geo value contains the search term
        if geo:
            geo_val = t.geo or {}
            geo_str = _json.dumps(geo_val, ensure_ascii=False).lower()
            if geo_lower not in geo_str:
                continue

        # Suggestion mode filter — need to look up query.suggestions
        if suggestion_mode and suggestion_mode != "all" and t.query_id:
            try:
                q_row = await session.execute(
                    select(_QueryModel.suggestions).where(_QueryModel.id == t.query_id)
                )
                suggestions = q_row.scalar_one_or_none() or {}
                if suggestion_mode == "without" and suggestions:
                    continue
                if suggestion_mode == "with" and not suggestions:
                    continue
            except Exception:
                pass

        filtered_tasks.append(t)

    return [
        {
            "id": str(t.id),
            "url": t.click_url or "",
            "status": t.status,
            "source": t.source or "",
            "position": t.position,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "geo": t.geo or {},
        }
        for t in filtered_tasks
    ]


# --- Global Search ------------------------------------------------------------ #


@router.get("/global-search")
async def global_search(
    q: str = Query(..., min_length=1),
    session: AsyncSession = Depends(get_session),
):
    """Search across groups, projects and queries. Returns grouped results with navigation hrefs."""
    from services.project_service.domain.models import ProjectGroup

    pattern = f"%{q}%"

    # Search groups
    group_result = await session.execute(
        select(ProjectGroup).where(ProjectGroup.name.ilike(pattern))
    )
    groups = group_result.scalars().all()

    # Search projects (matching name or domain)
    proj_result = await session.execute(
        select(Project).where(
            or_(
                Project.name.ilike(pattern),
                Project.domain.ilike(pattern),
            )
        ).limit(50)
    )
    projects = proj_result.scalars().all()

    # Search queries (matching text) — limit to avoid huge result sets
    query_result = await session.execute(
        select(_QueryModel).where(_QueryModel.text.ilike(pattern)).limit(30)
    )
    queries_raw = query_result.scalars().all()

    return {
        "groups": [
            {"id": str(g.id), "name": g.name, "href": f"/?group_id={str(g.id)}"}
            for g in groups
        ],
        "projects": [
            {
                "id": str(p.id),
                "name": p.name,
                "domain": p.domain,
                "href": f"/projects/{str(p.id)}",
            }
            for p in projects
        ],
        "queries": [
            {
                "id": str(qi.id),
                "text": qi.text,
                "project_id": str(qi.project_id),
                "href": f"/projects/{str(qi.project_id)}?tab=queries&query={qi.text}",
            }
            for qi in queries_raw
        ],
    }


# --- Bulk project operations -------------------------------------------------- #


@router.post("/bulk-toggle")
async def bulk_toggle_projects(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Toggle is_active for a list of projects by IDs."""
    from services.auth_service.domain.models import User

    user_id_raw = body.get("user_id")
    try:
        uid = UUID(str(user_id_raw)) if user_id_raw else uuid4()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid user_id")

    project_ids: list[str] = body.get("project_ids", [])
    if not project_ids:
        raise HTTPException(status_code=400, detail="project_ids is required")

    new_active = bool(body.get("is_active"))
    updated = 0

    for pid in project_ids:
        try:
            puuid = UUID(pid)
        except (ValueError, TypeError):
            continue
        result = await session.execute(
            select(Project).where(Project.id == puuid, Project.user_id == uid)
        )
        proj = result.scalar_one_or_none()
        if proj:
            proj.is_active = new_active  # type: ignore[attr-defined]
            updated += 1

    await session.commit()
    return {"updated": updated}


@router.post("/bulk-edit")
async def bulk_edit_projects(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Bulk-edit projects by ID set (daily_limit, region, geo_settings, scheduling_window, query_modifications)."""
    from services.auth_service.domain.models import User

    user_id_raw = body.get("user_id")
    try:
        uid = UUID(str(user_id_raw)) if user_id_raw else uuid4()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid user_id")

    project_ids: list[str] = body.get("project_ids", [])
    if not project_ids:
        raise HTTPException(status_code=400, detail="project_ids is required")

    updates: dict = {}
    if "daily_limit" in body:
        dl = int(body["daily_limit"])
        if dl < 0:
            raise HTTPException(status_code=400, detail="daily_limit must be >= 0")
        updates["daily_limit"] = dl
    if "region" in body:
        updates["region"] = str(body["region"])
    if "geo_settings" in body:
        try:
            _json.loads(_json.dumps(body["geo_settings"]))
            updates["geo_settings"] = body["geo_settings"]
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid geo_settings JSON")
    if "scheduling_window" in body:
        updates["scheduling_window"] = body["scheduling_window"]
    if "query_modifications" in body:
        updates["query_modifications"] = body["query_modifications"]

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updated = 0
    for pid in project_ids:
        try:
            puuid = UUID(pid)
        except (ValueError, TypeError):
            continue
        result = await session.execute(
            select(Project).where(Project.id == puuid, Project.user_id == uid)
        )
        proj = result.scalar_one_or_none()
        if proj:
            for k, v in updates.items():
                setattr(proj, k, v)  # type: ignore[arg-type]
            updated += 1

    await session.commit()
    return {"updated": updated}


@router.post("/bulk-delete")
async def bulk_delete_projects(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Delete projects by ID set (cascades to queries, tasks)."""
    from services.auth_service.domain.models import User

    user_id_raw = body.get("user_id")
    try:
        uid = UUID(str(user_id_raw)) if user_id_raw else uuid4()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid user_id")

    project_ids: list[str] = body.get("project_ids", [])
    if not project_ids:
        raise HTTPException(status_code=400, detail="project_ids is required")

    deleted = 0
    for pid in project_ids:
        try:
            puuid = UUID(pid)
        except (ValueError, TypeError):
            continue
        result = await session.execute(
            select(Project).where(Project.id == puuid, Project.user_id == uid)
        )
        proj = result.scalar_one_or_none()
        if proj:
            await session.delete(proj)
            deleted += 1

    await session.commit()
    return {"deleted": deleted}


@router.post("/bulk-delegate")
async def bulk_delegate_projects(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Add delegate access to multiple projects for a single user."""
    from services.auth_service.domain.models import User

    user_id_raw = body.get("user_id")
    try:
        uid = UUID(str(user_id_raw)) if user_id_raw else uuid4()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid user_id")

    project_ids: list[str] = body.get("project_ids", [])
    delegate_uid_raw = body.get("delegate_user_id")
    if not delegate_uid_raw:
        raise HTTPException(status_code=400, detail="delegate_user_id is required")
    try:
        delegate_uid = UUID(delegate_uid_raw)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid delegate_user_id")

    role = body.get("role", "view")
    added = 0

    for pid in project_ids:
        try:
            puuid = UUID(pid)
        except (ValueError, TypeError):
            continue
        result = await session.execute(
            select(Project).where(Project.id == puuid, Project.user_id == uid)
        )
        proj = result.scalar_one_or_none()
        if not proj:
            continue
        existing = await session.execute(
            select(ProjectDelegate).where(
                and_(  # type: ignore[assignment]
                    ProjectDelegate.project_id == puuid,
                    ProjectDelegate.delegate_user_id == delegate_uid,
                )
            )
        )
        if not existing.scalar_one_or_none():
            invite = ProjectDelegate(
                id=uuid4(),
                project_id=puuid,
                delegate_user_id=delegate_uid,
                inviter_user_id=uid,
                role=role,
            )
            session.add(invite)
            added += 1

    await session.commit()
    return {"added": added}


# --- Bulk query operations -------------------------------------------------- #


@router.post("/{project_id}/queries/bulk-update")
async def bulk_update_queries(
    project_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Bulk-update queries by ID set (daily_clicks, geo, click_url)."""
    from services.auth_service.domain.models import User

    user = UUID(body.get("user_id", "00000000-0000-0000-0000-000000000000"))
    try:
        uid = UUID(str(user))
    except (ValueError, TypeError):
        # Accept user_id as string if present
        uid = UUID(body.get("user_id", "00000000-0000-0000-0000-000000000000"))

    try:
        proj_uuid = UUID(project_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid project_id")

    # Verify ownership
    from sqlalchemy import select as sa_select
    q = await session.execute(
        sa_select(Project).where(Project.id == proj_uuid, Project.user_id == uid)
    )
    if not q.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    query_ids: list[str] = body.get("query_ids", [])
    if not query_ids:
        raise HTTPException(status_code=400, detail="query_ids is required")

    updates: dict = {}
    if "daily_clicks" in body:
        dc = int(body["daily_clicks"])
        if dc < 0:
            raise HTTPException(status_code=400, detail="daily_clicks must be >= 0")
        updates["daily_clicks"] = dc
    if "geo" in body:
        try:
            _json.loads(_json.dumps(body["geo"]))  # validate JSON serializable
            updates["geo"] = body["geo"]
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid geo JSON")
    if "click_url" in body:
        cu = str(body["click_url"])
        if not cu:
            raise HTTPException(status_code=400, detail="click_url cannot be empty")
        updates["click_url"] = cu
    if "text" in body:
        updates["text"] = str(body["text"])

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updated = 0
    for qid in query_ids:
        try:
            quuid = UUID(qid)
        except (ValueError, TypeError):
            continue
        row = await session.execute(
            sa_select(_QueryModel).where(
                _QueryModel.id == quuid, _QueryModel.project_id == proj_uuid
            )
        )
        model = row.scalar_one_or_none()
        if model:
            for k, v in updates.items():
                setattr(model, k, v)
            updated += 1

    await session.commit()
    return {"updated": updated}


# --- Report Export ------------------------------------------------------------ #


@router.get("/{project_id}/reports/analytics.csv")
async def export_analytics_report(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    from_date: str = Query(default=None),
    to_date: str = Query(default=None),
):
    """Export analytics report (clicks, positions, completed_rate) as CSV."""
    from datetime import datetime as _dt, timezone as _tz

    project = await session.get(Project, UUID(project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    date_filter: list = []
    if from_date:
        try:
            fd = _dt.fromisoformat(from_date).replace(tzinfo=_tz.utc)
            date_filter.append(QueueTask.created_at >= fd)
        except (ValueError, TypeError):
            pass
    if to_date:
        try:
            td = _dt.fromisoformat(to_date).replace(tzinfo=_tz.utc)
            date_filter.append(QueueTask.created_at <= td)
        except (ValueError, TypeError):
            pass

    base_where = [QueueTask.project_id == UUID(project_id)] + date_filter
    result = await session.execute(
        select(
            _QueryModel.text,
            func.count(QueueTask.id).label("total_tasks"),
            func.sum(
                sa_case((QueueTask.status == "completed", 1), else_=0)
            ).label("completed"),
            func.avg(
                sa_case(
                    ((QueueTask.status == "completed") & (QueueTask.position.isnot(None)), QueueTask.position),
                    else_=None,
                )
            ).label("avg_position"),
        )
        .join(QueueTask, _QueryModel.id == QueueTask.query_id, isouter=True)
        .where(*base_where)  # type: ignore[arg-type]
        .group_by(_QueryModel.id, _QueryModel.text)
    )

    rows = result.all()

    output = _io.StringIO()
    writer = _csv.writer(output)
    writer.writerow(["query_text", "total_tasks", "completed", "completed_rate", "avg_position"])
    for r in rows:
        completed_rate = round((r.completed / (r.total_tasks or 1) * 100), 2) if (r.total_tasks or 0) > 0 else 0
        writer.writerow([
            r.text,
            r.total_tasks or 0,
            r.completed or 0,
            completed_rate,
            round(float(r.avg_position), 2) if r.avg_position else None,
        ])

    from fastapi.responses import Response as FastAPIResponse

    safe_name = project.name.replace(" ", "_")[:50]
    return FastAPIResponse(
        content=output.getvalue(),
        headers={
            "Content-Disposition": f"attachment; filename={safe_name}_analytics.csv",
        },
        media_type="text/csv",
    )


@router.get("/{project_id}/reports/summary.csv")
async def export_summary_report(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    from_date: str = Query(default=None),
    to_date: str = Query(default=None),
):
    """Export high-level summary report as CSV."""
    from datetime import datetime as _dt, timezone as _tz

    project = await session.get(Project, UUID(project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    date_filter: list = []
    if from_date:
        try:
            fd = _dt.fromisoformat(from_date).replace(tzinfo=_tz.utc)
            date_filter.append(QueueTask.created_at >= fd)
        except (ValueError, TypeError):
            pass
    if to_date:
        try:
            td = _dt.fromisoformat(to_date).replace(tzinfo=_tz.utc)
            date_filter.append(QueueTask.created_at <= td)
        except (ValueError, TypeError):
            pass

    base_where = [QueueTask.project_id == UUID(project_id)] + date_filter

    agg_result = await session.execute(
        select(
            func.count(QueueTask.id).label("total_tasks"),
            func.sum(sa_case((QueueTask.status == "completed", 1), else_=0)).label("total_completed"),
            func.avg(
                sa_case(
                    ((QueueTask.status == "completed") & (QueueTask.position.isnot(None)), QueueTask.position),
                    else_=None,
                )
            ).label("overall_avg_position"),
        )
        .where(*base_where)  # type: ignore[arg-type]
    )
    agg = agg_result.one()

    top_pos_result = await session.execute(
        select(_QueryModel.text, QueueTask.position).where(
            and_(  # type: ignore[arg-type]
                QueueTask.project_id == UUID(project_id),
                QueueTask.status == "completed",
                QueueTask.position.isnot(None),
                *date_filter,
            )
        ).order_by(QueueTask.position).limit(100)
    )
    top_rows = top_pos_result.all()

    output = _io.StringIO()
    writer = _csv.writer(output)
    writer.writerow(["report_type", "TopInjector Summary Report"])
    writer.writerow(["project_name", project.name])
    writer.writerow(["domain", project.domain])
    if from_date:
        writer.writerow(["period_from", from_date])
    if to_date:
        writer.writerow(["period_to", to_date])
    writer.writerow([])
    writer.writerow(["metric", "value"])
    writer.writerow(["total_tasks", agg.total_tasks or 0])
    writer.writerow(["total_completed", agg.total_completed or 0])
    completed_rate = round(
        ((agg.total_completed or 0) / max(agg.total_tasks or 1, 1) * 100), 2
    )
    writer.writerow(["completion_rate_pct", completed_rate])
    writer.writerow(["avg_position", round(float(agg.overall_avg_position), 2) if agg.overall_avg_position else None])
    writer.writerow([])
    writer.writerow(["query_text", "best_position"])
    pos_map: dict[str, int] = {}
    for r in top_rows:
        txt, pos_val = r[0], r[1]
        if txt and pos_val is not None and (txt not in pos_map or pos_val < pos_map[txt]):
            pos_map[txt] = pos_val
    for txt in sorted(pos_map):
        writer.writerow([txt, pos_map[txt]])

    from fastapi.responses import Response as FastAPIResponse

    safe_name = project.name.replace(" ", "_")[:50]
    return FastAPIResponse(
        content=output.getvalue(),
        headers={
            "Content-Disposition": f"attachment; filename={safe_name}_summary.csv",
        },
        media_type="text/csv",
    )


# --- Balance ---------------------------------------------------------------- #

@router.get("/{id}/balance")
async def get_project_balance(
    id: UUID,
    project = Depends(_get_project_or_404),  # type: ignore[name-defined]
):
    """Get current project balance."""
    return {
        "project_id": str(project.id),
        "balance": project.balance_credits,
        "balance_rub": project.balance_credits / 100,
    }


@router.post("/{id}/balance/add")
async def add_project_balance(
    id: UUID,
    body: dict,
    project = Depends(_get_project_or_404),  # type: ignore[name-defined]
    session: AsyncSession = Depends(get_session),
):
    """Add credits to a project balance."""
    amount_kopeks = int(body.get("amount", 0) * 100)
    description = body.get("description", "")

    if amount_kopeks <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    # Update project balance
    project.balance_credits += amount_kopeks

    # Create transaction record
    txn = BalanceTransaction(
        id=uuid4(),
        project_id=id,
        amount=amount_kopeks,
        description=description,
        type="add",
    )
    session.add(txn)
    await session.commit()
    await session.refresh(project)

    return {
        "project_id": str(project.id),
        "balance": project.balance_credits,
        "balance_rub": project.balance_credits / 100,
        "added": amount_kopeks / 100,
        "transaction_id": str(txn.id),
    }


@router.post("/{id}/balance/set")
async def set_project_balance(
    id: UUID,
    body: dict,
    project = Depends(_get_project_or_404),  # type: ignore[name-defined]
    session: AsyncSession = Depends(get_session),
):
    """Set project balance to a specific value."""
    new_balance_kopeks = int(body.get("balance", 0) * 100)
    diff = new_balance_kopeks - project.balance_credits
    description = body.get("description", "Баланс установлен вручную")

    if diff != 0:
        txn = BalanceTransaction(
            id=uuid4(),
            project_id=id,
            amount=diff,
            description=f"{description} (установка баланса)",
            type="set",
        )
        session.add(txn)

    project.balance_credits = new_balance_kopeks
    await session.commit()

    return {
        "project_id": str(project.id),
        "balance": project.balance_credits,
        "balance_rub": project.balance_credits / 100,
    }


@router.get("/{id}/balance/history")
async def get_balance_history(
    id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    project = Depends(_get_project_or_404),  # type: ignore[name-defined]
    session: AsyncSession = Depends(get_session),
):
    """Get balance transaction history for a project."""
    offset = (page - 1) * page_size

    # Count total
    count_query = select(func.count()).select_from(BalanceTransaction).where(
        BalanceTransaction.project_id == id
    )
    total = await session.scalar(count_query)

    # Get transactions
    txn_query = (
        select(BalanceTransaction)
        .where(BalanceTransaction.project_id == id)
        .order_by(BalanceTransaction.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(txn_query)
    txns = result.scalars().all()

    return {
        "project_id": str(project.id),
        "transactions": [{
            "id": str(t.id),
            "amount_kopeks": t.amount,
            "amount_rub": t.amount / 100,
            "type": t.type,
            "description": t.description or "",
            "created_at": t.created_at.isoformat() if t.created_at else None,
        } for t in txns],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }

