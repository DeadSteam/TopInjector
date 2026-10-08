"""Project service routes — CRUD for projects and queries."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.session import get_session
from services.project_service.domain.models import Project, Query

router = APIRouter(tags=["projects"])


@router.post("/")
async def create_project(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Create a new project."""
    project = Project(
        name=body["name"],
        domain=body["domain"],
        strategy_type=body.get("strategy_type", "daily"),
        daily_limit=body.get("daily_limit", 500),
        region=body.get("region"),
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return {"id": str(project.id), "name": project.name, "domain": project.domain}


@router.get("/")
async def list_projects(
    session: AsyncSession = Depends(get_session),
):
    """List all projects."""
    result = await session.execute(select(Project))
    projects = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "domain": p.domain,
            "strategy_type": p.strategy_type,
            "daily_limit": p.daily_limit,
            "is_active": p.is_active,
        }
        for p in projects
    ]


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a single project by ID."""
    from uuid import UUID

    result = await session.execute(select(Project).where(Project.id == UUID(project_id)))
    project = result.scalar_one_or_none()
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
    }


@router.put("/{project_id}")
async def update_project(
    project_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Update an existing project."""
    from uuid import UUID

    result = await session.execute(select(Project).where(Project.id == UUID(project_id)))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    for key, value in body.items():
        if hasattr(project, key) and key not in ("id", "created_at", "updated_at"):
            setattr(project, key, value)

    await session.commit()
    return {"id": str(project.id), "updated": True}


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete a project."""
    from uuid import UUID

    result = await session.execute(select(Project).where(Project.id == UUID(project_id)))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await session.delete(project)
    await session.commit()
    return {"deleted": True}


# --- Query endpoints -------------------------------------------------------- #


@router.post("/{project_id}/queries")
async def add_query(
    project_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Add a query (term) to a project."""
    from uuid import UUID

    query = Query(
        project_id=UUID(project_id),
        text=body["text"],
        url=body.get("url"),
        click_url=body.get("click_url"),
        geo=body.get("geo"),
    )
    session.add(query)
    await session.commit()
    await session.refresh(query)
    return {"id": str(query.id), "text": query.text}


@router.get("/{project_id}/queries")
async def list_queries(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """List all queries for a project."""
    from uuid import UUID

    result = await session.execute(
        select(Query).where(Query.project_id == UUID(project_id))
    )
    queries = result.scalars().all()
    return [
        {
            "id": str(q.id),
            "text": q.text,
            "url": q.url,
            "click_url": q.click_url,
            "geo": q.geo,
            "daily_clicks": q.daily_clicks,
        }
        for q in queries
    ]
