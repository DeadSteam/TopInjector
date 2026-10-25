"""QueueTaskRepository — task queue operations."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import ColumnElement, Select, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from services.project_service.domain.models import Project as _ProjectModel
from services.queue_service.domain.models import QueueTask


def integration_condition(integration: str) -> ColumnElement[bool]:
    """Projects of an integration type; "default" means projects without one."""
    column = _ProjectModel.integrations["integration_type"].as_string()
    if integration == "default":
        return or_(column.is_(None), column.in_(["", "default"]))
    return column == integration


def _parse_moment(value: str | None) -> datetime | None:
    try:
        moment = datetime.fromisoformat(value) if value else None
    except ValueError:
        return None
    return moment.replace(tzinfo=moment.tzinfo or timezone.utc) if moment else None


def task_filters(
    project_id: UUID | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    integration: str | None = None,
) -> list[ColumnElement[bool]]:
    """WHERE conditions shared by the queue list, stats and live feed.

    Dates filter by creation time; a date-only ``to_date`` includes that whole day.
    """
    conditions: list[ColumnElement[bool]] = []
    if project_id:
        conditions.append(QueueTask.project_id == project_id)
    if integration:
        conditions.append(QueueTask.project_id.in_(select(_ProjectModel.id).where(integration_condition(integration))))
    if start := _parse_moment(from_date):
        conditions.append(QueueTask.created_at >= start)
    if end := _parse_moment(to_date):
        if len(to_date or "") == 10:  # YYYY-MM-DD
            conditions.append(QueueTask.created_at < end + timedelta(days=1))
        else:
            conditions.append(QueueTask.created_at <= end)
    return conditions


class QueueTaskRepository:
    """Database operations for QueueTask entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(
        self,
        project_id: UUID | None = None,
        status: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        integration: str | None = None,
        project_ids: Select | None = None,
        limit: int | None = None,
    ) -> list[QueueTask]:
        """Newest tasks first; ``project_ids`` (a select of ids) limits results to those projects."""
        query = select(QueueTask).options(joinedload(QueueTask.project))
        query = query.where(*task_filters(project_id, from_date, to_date, integration))
        if project_ids is not None:
            query = query.where(QueueTask.project_id.in_(project_ids))
        if status:
            query = query.where(QueueTask.status == status)
        query = query.order_by(QueueTask.created_at.desc()).limit(limit)
        return list((await self._session.execute(query)).scalars().all())

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

    async def update_status(
        self,
        task_id: UUID,
        new_status: str,
        position: int | None = None,
        project_ids: Select | None = None,
        details: str | None = None,
    ) -> bool:
        """Set a task's status; ``project_ids`` (a select of ids) restricts which tasks may be touched."""
        query = select(QueueTask).where(QueueTask.id == task_id)
        if project_ids is not None:
            query = query.where(QueueTask.project_id.in_(project_ids))
        result = await self._session.execute(query)
        task = result.scalar_one_or_none()
        if task and task.status not in ("completed", "not_found"):
            task.status = new_status  # type: ignore[attr-defined]
            if position is not None:
                task.position = position  # type: ignore[attr-defined]
            if details is not None:
                task.details = details  # type: ignore[attr-defined]
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
