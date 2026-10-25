"""Subscription plans for the panel.

A ``Plan`` is a template of limits + price; ``UserPlan`` is the plan a user is currently on.
These describe the SaaS subscription only (seat and project limits, price per day/month) — no
traffic metering.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database.base import UUIDModel


class Plan(UUIDModel):
    """A subscription tier: limits and price."""

    __tablename__ = "plans"

    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)  # start/lite/plus/...
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)  # offered for sale
    price_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # kopeks / day
    price_per_month: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # kopeks / month
    max_users: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # team seats
    max_projects: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # projects allowed


class UserPlan(UUIDModel):
    """The plan a user is currently subscribed to (one active plan per user)."""

    __tablename__ = "user_plans"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    plan: Mapped["Plan"] = relationship(lazy="selectin")
