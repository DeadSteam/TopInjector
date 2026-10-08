"""QueueTaskRepository — task queue operations."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.queue_service.domain.models import QueueTask


class QueueTaskRepository:
    """Database operations for QueueTask entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self, project_id: UUID | None = None, status: str | None = None) -> list[QueueTask]:
        query = select(QueueTask)
        if project_id:
            query = query.where(QueueTask.project_id == project_id)
        if status:
            query = query.where(QueueTask.status == status)
        result = await self._session.execute(query.order_by(QueueTask.created_at))
        return list(result.scalars().all())

    async def get_pending_for_project(self, project_id: UUID) -> list[QueueTask]:
        result = await self._session.execute(
            select(QueueTask).where(
                QueueTask.project_id == project_id,
                QueueTask.status == "pending",
            )
        )
        return list(result.scalars().all())

    async def get_in_progress(self) -> list[QueueTask]:
        result = await self._session.execute(select(QueueTask).where(QueueTask.status == "in_progress"))
        return list(result.scalars().all())

    async def create(self, task: QueueTask) -> None:
        self._session.add(task)

    async def update_status(self, task_id: UUID, new_status: str, position: int | None = None) -> bool:
        result = await self._session.execute(
            select(QueueTask).where(QueueTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if task and task.status not in ("completed", "not_found"):
            task.status = new_status  # type: ignore[attr-defined]
            if position is not None:
                task.position = position  # type: ignore[attr-defined]
            return True
        return False

    async def clear_for_project(self, project_id: UUID) -> int:
        result = await self._session.execute(
            delete(QueueTask).where(
                QueueTask.project_id == project_id,
                QueueTask.status.in_(["pending", "in_progress"]),
            )
        )
        return result.rowcount
