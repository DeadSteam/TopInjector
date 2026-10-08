"""Project service routes — CRUD for projects and queries."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.session import get_session
from services.project_service.domain.models import Project, Query
from services.project_service.repositories.project_repo import ProjectRepository
from services.project_service.repositories.query_repo import QueryRepository

router = APIRouter(tags=["projects"])


async def _project_repo(session: AsyncSession = Depends(get_session)) -> ProjectRepository:
    return ProjectRepository(session)


async def _query_repo(session: AsyncSession = Depends(get_session)) -> QueryRepository:
    return QueryRepository(session)


@router.post("/")
async def create_project(
    body: dict,
    project_repo: ProjectRepository = Depends(_project_repo),
):
    """Create a new project."""
    from uuid import uuid4

    project = Project(
        id=uuid4(),
        name=body["name"],
        domain=body["domain"],
        strategy_type=body.get("strategy_type", "daily"),
        daily_limit=body.get("daily_limit", 500),
        region=body.get("region"),
    )
    project = await project_repo.create(project)
    return {"id": str(project.id), "name": project.name, "domain": project.domain}


@router.get("/")
async def list_projects(
    project_repo: ProjectRepository = Depends(_project_repo),
):
    """List all projects."""
    result = await project_repo.get_all_for_user(None)  # type: ignore[arg-type]
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "domain": p.domain,
            "strategy_type": p.strategy_type,
            "daily_limit": p.daily_limit,
            "is_active": p.is_active,
        }
        for p in result
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
    query = Query(
        project_id=UUID(project_id),
        text=body["text"],
        url=body.get("url"),
        click_url=body.get("click_url"),
        geo=body.get("geo", {}),
    )
    query = await query_repo.create(query)
    return {"id": str(query.id), "text": query.text}


@router.get("/{project_id}/queries")
async def list_queries(
    project_id: str,
    query_repo: QueryRepository = Depends(_query_repo),
):
    """List all queries for a project."""
    queries = await query_repo.get_by_project(UUID(project_id))
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
