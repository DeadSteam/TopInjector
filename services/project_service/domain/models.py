"""Project and Query domain models."""

from sqlalchemy import Column, ForeignKey, Integer, String, Text, Boolean, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from core.models import UUIDModel, Base


class Project(UUIDModel):
    """User's project (a website/domain to manage)."""

    __tablename__ = "projects"

    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    domain = Column(String(255), unique=True, nullable=False, index=True)
    region = Column(String(50), default="ru")
    strategy_type = Column(String(20), nullable=False, default="daily")  # daily/monthly/hourly
    geo_settings = Column(JSONB, nullable=False, default=dict)
    integrations = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("ix_projects_user_id", "user_id"),
    )

    # relationships
    queries = relationship("Query", back_populates="project", cascade="all, delete-orphan")


class Query(Base):
    """Keyword query associated with a project."""

    __tablename__ = "queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), ForeignKey("projects.id"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    url = Column(Text, nullable=True)
    click_url = Column(Text, nullable=True)
    geo = Column(JSONB, nullable=False, default=dict)
    daily_clicks = Column(Integer, default=0)
    position = Column(Integer, nullable=True)
    boost_min = Column(Integer, nullable=True)
    boost_max = Column(Integer, nullable=True)
    frequency = Column(Integer, default=1)

    __table_args__ = (
        Index("ix_queries_project_id", "project_id"),
    )

    # relationship
    project = relationship("Project", back_populates="queries")
