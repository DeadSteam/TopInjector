"""Model registry: importing this module registers every table on ``Base.metadata``.

Alembic and the test suite import it so that metadata is complete regardless of
which routers happen to be loaded.
"""

from services.auth_service.domain.models import User
from services.project_service.domain.models import Project, Query
from services.queue_service.domain.models import QueueTask
from shared.database.base import Base

__all__ = ["Base", "Project", "Query", "QueueTask", "User"]
