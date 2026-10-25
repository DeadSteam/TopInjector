"""Model registry: importing this module registers every table on ``Base.metadata``.

Alembic and the test suite import it so that metadata is complete regardless of
which routers happen to be loaded.
"""

from services.auth_service.domain.models import User
from services.project_service.domain.external_services import (  # noqa: F401
    ExternalServiceAccount,
    YandexWebmasterDomain,
)
from services.project_service.domain.models import Project, ProjectToken, Query  # noqa: F401
from services.project_service.domain.plans import Plan, UserPlan  # noqa: F401
from services.project_service.domain.whitelabel import WhiteLabel  # noqa: F401
from services.queue_service.domain.models import QueueTask
from shared.database.base import Base

__all__ = [
    "Base", "Project", "Query", "QueueTask", "User", "ProjectToken",
    "ExternalServiceAccount", "YandexWebmasterDomain", "Plan", "UserPlan", "WhiteLabel",
]
