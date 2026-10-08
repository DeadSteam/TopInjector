"""QueryRepository — query management operations."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.project_service.domain.models import Query


class QueryRepository:
    """Database operations for Query entities within a Project."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_project(self, project_id: UUID) -> list[Query]:
        result = await self._session.execute(select(Query).where(Query.project_id == project_id))
        return list(result.scalars().all())

    async def create(self, query: Query) -> Query:
        self._session.add(query)
        await self._session.flush()
        await self._session.refresh(query)
        return query

    async def delete_all_for_project(self, project_id: UUID) -> int:
        result = await self._session.execute(delete(Query).where(Query.project_id == project_id))
        return result.rowcount
