"""ProjectRepository — CRUD for Project entities."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.project_service.domain.models import Project, Query


class ProjectRepository:
    """Database operations for the Project aggregate root."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, project_id: UUID) -> Project | None:
        result = await self._session.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()

    async def create(self, project: Project) -> Project:
        self._session.add(project)
        await self._session.flush()
        await self._session.refresh(project)
        return project

    async def delete(self, project: Project) -> None:
        await self._session.delete(project)

    async def get_queries(self, project_id: UUID) -> list[Query]:
        result = await self._session.execute(select(Query).where(Query.project_id == project_id))
        return list(result.scalars().all())

    async def add_query(self, query: Query) -> None:
        self._session.add(query)

    async def get_all_for_user(self, user_id: UUID) -> list[Project]:
        result = await self._session.execute(select(Project).where(Project.user_id == user_id))
        return list(result.scalars().all())
