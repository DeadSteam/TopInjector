"""Geo code presets — Russian cities/regions with Yandex geo codes."""

from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from shared.database.base import UUIDModel


class GeoCodePreset(UUIDModel):
    """Predefined city/region geo codes for the multigeo builder."""

    __tablename__ = "geo_code_presets"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    """Human-readable name, e.g. 'Москва'."""
    yandex_geo_id: Mapped[int | None] = mapped_column(JSON, nullable=True)
    """Yandex geo identifier (if available)."""
    country_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default="ru")
    """ISO country code, default 'ru'."""
    region_name: Mapped[str] = mapped_column(String(200), nullable=False)
    """Federal region name, e.g. 'Московская область'."""
    city_name: Mapped[str] = mapped_column(String(200), nullable=False)
    """City or locality name."""
    is_city_center: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    """Yandex-style center flag. Stores as JSON for future expansion."""
    search_aliases: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Comma-separated aliases for search indexing, e.g. 'moscow,mowsksv,moscova'."""
