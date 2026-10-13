"""Audit log entry model for tracking project changes."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database.base import UUIDModel
from shared.database.types import JSONType


class AuditLogEntry(UUIDModel):
    """Tracks changes to projects and queries."""

    __tablename__ = "project_audit_log"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # create, update, delete, delegate_add, delegate_remove, clear_queue, proklik, etc.
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # who performed the action
    old_values: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    new_values: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # additional context

    project: Mapped["Project"] = relationship()  # type: ignore[name-defined]
