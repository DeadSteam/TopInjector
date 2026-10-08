"""Auth service domain models."""

from sqlalchemy import Column, String, DateTime, func, Boolean, Index
from uuid import UUID

from core.models import UUIDModel


class User(UUIDModel):
    """User entity. All IDs are UUID for FK consistency."""

    __tablename__ = "users"

    email = Column(String(320), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100))
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)

    # indexes for common queries
    __table_args__ = (
        Index("ix_users_email", "email"),
    )
