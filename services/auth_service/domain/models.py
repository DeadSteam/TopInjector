"""Auth service domain models."""

from typing import Any

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.database.base import UUIDModel
from shared.database.types import JSONType


class User(UUIDModel):
    """User entity. All IDs are UUID for FK consistency."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(Text)  # URL to user's profile photo
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    messenger_settings: Mapped[dict[str, Any] | None] = mapped_column(JSONType)  # telegram/max + stop_words
    external_services: Mapped[dict[str, Any] | None] = mapped_column(JSONType)  # xml_river / xml_stock
    prepay_per_click_cop: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # prepaid cost per click in kopeks (rubles * 100)
    bonus_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # bonus credits in kopeks
