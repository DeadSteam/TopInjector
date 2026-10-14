"""Project and Query domain models."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database.base import UUIDModel
from shared.database.types import JSONType


class ProjectGroup(UUIDModel):
    """User's project group for organising projects."""

    __tablename__ = "project_groups"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50))  # Lucide icon name

    projects: Mapped[list["Project"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", passive_deletes=True
    )


class Project(UUIDModel):
    """User's project (a website/domain to manage)."""

    __tablename__ = "projects"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("project_groups.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    region: Mapped[str | None] = mapped_column(String(50), default="ru")
    strategy_type: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")  # daily/monthly/hourly
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    geo_settings: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    integrations: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    scheduling_window: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)  # {start: "07:00", end: "22:00"}
    query_modifications: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)  # flags: capital_first, random_caps, typos, trailing_space
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_stop_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # automatic project stop date/time
    balance_credits: Mapped[float] = mapped_column(Integer, nullable=False, default=0)  # project credits in kopeks (integer)

    __table_args__ = (UniqueConstraint("user_id", "domain", name="uq_projects_user_domain"),)

    group: Mapped["ProjectGroup"] = relationship(back_populates="projects")

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
    query_modifications: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)  # flags per-query: capital_first, random_caps, typos, trailing_space

    project: Mapped[Project] = relationship(back_populates="queries")


class ProjectToken(UUIDModel):
    """API token for external API access (X-Auth-Token header)."""

    __tablename__ = "project_tokens"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_string: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    __table_args__ = (
        # One active token per project per user at a time.
        UniqueConstraint("user_id", "project_id", name="uq_user_project_token"),
    )


class ProjectDelegate(UUIDModel):
    """Delegated access to a project for another user."""

    __tablename__ = "project_delegates"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delegate_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    inviter_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="view")  # view / edit

    __table_args__ = (
        UniqueConstraint("project_id", "delegate_user_id", name="uq_project_delegate"),
    )


class Marker(UUIDModel):
    """Visual marker for tracking a page or section on a website."""

    __tablename__ = "markers"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    css_selector: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Webmarker(UUIDModel):
    """Webmarker integration for a project (e.g. Yandex.Webmaster or similar)."""

    __tablename__ = "webmarkers"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)  # yandex, google, etc.
    verification_code: Mapped[str | None] = mapped_column(String(100))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BalanceTransaction(UUIDModel):
    """Balance change transaction for a project."""

    __tablename__ = "balance_transactions"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # change in kopeks (positive=add, negative=spend)
    description: Mapped[str | None] = mapped_column(String(500))
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="add")  # add / set / spend / refund


class GeoCodePreset(UUIDModel):
    """Predefined city/region geo codes for the multigeo builder."""

    __tablename__ = "geo_code_presets"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    yandex_geo_id: Mapped[int | None] = mapped_column(JSONType, nullable=True)
    country_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default="ru")
    region_name: Mapped[str] = mapped_column(String(200), nullable=False)
    city_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_city_center: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    search_aliases: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("city_name", "region_name", name="uq_geo_code_preset_city_region"),
    )

