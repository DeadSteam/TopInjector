"""Queue task domain model and enums."""

from datetime import datetime, timezone
from enum import Enum as PyEnum
from uuid import UUID, uuid4

from sqlalchemy import Column, ForeignKey, Integer, String, Text, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, ENUM
from sqlalchemy.orm import relationship

from core.models import Base


class TaskSource(str, PyEnum):
    """Source of a queue task."""
    STRATEGY = "strategy"
    AUTOBURST = "autoburst"
    PROKLIK = "proklik"


class TaskStatus(str, PyEnum):
    """Current status of a queue task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NOT_FOUND = "not_found"
    STUCK = "stuck"


class QueueTask(Base):
    """A single task in the processing queue."""

    __tablename__ = "queue_tasks"

    id = Column(String(50), primary_key=True)
    project_id = Column(String(50), ForeignKey("projects.id"), nullable=False, index=True)
    query_id = Column(String(50), nullable=True)
    click_url = Column(Text, nullable=False)
    source = Column(
        ENUM(TaskSource, values_callable=lambda e: [x.value for x in e]),
        default=TaskSource.STRATEGY,
        nullable=False,
    )
    status = Column(
        ENUM(TaskStatus, values_callable=lambda e: [x.value for x in e]),
        default=TaskStatus.PENDING,
        nullable=False,
    )
    geo = Column(JSONB, nullable=False, default=dict)
    details = Column(Text, nullable=True)
    position = Column(Integer, nullable=True)
    pending_check_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("click_url", "status", name="uq_click_pending"),
    )

    # relationship
    project = relationship("Project")
