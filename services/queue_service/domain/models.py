"""Queue task domain model and enums."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.project_service.domain.models import Project
from shared.database.base import UUIDModel
from shared.database.types import JSONType


class TaskSource(StrEnum):
    """Source of a queue task."""

    STRATEGY = "strategy"
    AUTOBURST = "autoburst"
    PROKLIK = "proklik"


class TaskStatus(StrEnum):
    """Current status of a queue task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NOT_FOUND = "not_found"
    STUCK = "stuck"


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


class QueueTask(UUIDModel):
    """A single task in the processing queue."""

    __tablename__ = "queue_tasks"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    query_id: Mapped[UUID | None] = mapped_column(ForeignKey("queries.id", ondelete="SET NULL"))
    click_url: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[TaskSource] = mapped_column(
        Enum(TaskSource, name="task_source", values_callable=_enum_values),
        default=TaskSource.STRATEGY,
        nullable=False,
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", values_callable=_enum_values),
        default=TaskStatus.PENDING,
        nullable=False,
        index=True,
    )
    geo: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    details: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int | None] = mapped_column(Integer)
    pending_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # At most one *pending* task per URL within a project; finished tasks may repeat.
        Index(
            "uq_queue_tasks_pending_click_url",
            "project_id",
            "click_url",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    project: Mapped[Project] = relationship()
