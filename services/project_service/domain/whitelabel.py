"""White-label branding for the panel: one row per user with logos, colours and a custom domain."""

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.database.base import UUIDModel

# Longest allowed markdown blurb (description / welcome text).
MAX_BLURB_LEN = 700


class WhiteLabel(UUIDModel):
    """Per-user branding settings for a white-labelled panel."""

    __tablename__ = "white_labels"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dns_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending/verified/error
    platform_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    accent_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#3B82F6")
    description_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    welcome_text_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_light_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_dark_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    favicon_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banner_catalog_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banner_homepage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
