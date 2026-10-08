"""Project and Query domain models."""

from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database.base import UUIDModel
from shared.database.types import JSONType


class Project(UUIDModel):
    """User's project (a website/domain to manage)."""

    __tablename__ = "projects"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    region: Mapped[str | None] = mapped_column(String(50), default="ru")
    strategy_type: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")  # daily/monthly/hourly
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    geo_settings: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    integrations: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "domain", name="uq_projects_user_domain"),)

    queries: Mapped[list["Query"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )


class Query(UUIDModel):
    """Keyword query associated with a project."""

    __tablename__ = "queries"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    click_url: Mapped[str | None] = mapped_column(Text)
    geo: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    daily_clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    position: Mapped[int | None] = mapped_column(Integer)
    boost_min: Mapped[int | None] = mapped_column(Integer)
    boost_max: Mapped[int | None] = mapped_column(Integer)
    frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    project: Mapped[Project] = relationship(back_populates="queries")
