"""External data-source accounts: Yandex Webmaster and SERP position APIs (XMLRiver / XMLStock).

These are read-only integrations used for rank tracking — a user stores their own API
credentials for a service and, for Yandex Webmaster, the domains confirmed under that account.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database.base import UUIDModel
from shared.database.types import JSONType

# Service types a user may connect. Free-form on the column; this list is what the API accepts.
EXTERNAL_SERVICE_TYPES = frozenset({"yandex_webmaster", "xmlriver", "xmlstock"})


class ExternalServiceAccount(UUIDModel):
    """A user's connected account for an external rank-tracking data source."""

    __tablename__ = "external_service_accounts"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_type: Mapped[str] = mapped_column(String(50), nullable=False)  # yandex_webmaster / xmlriver / xmlstock
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)  # creds/config
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    domains: Mapped[list["YandexWebmasterDomain"]] = relationship(
        back_populates="account", cascade="all, delete-orphan", passive_deletes=True
    )


class YandexWebmasterDomain(UUIDModel):
    """A domain confirmed under a Yandex Webmaster account."""

    __tablename__ = "yandex_webmaster_domains"

    service_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("external_service_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped["ExternalServiceAccount"] = relationship(back_populates="domains")
