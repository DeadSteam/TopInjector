"""Main FastAPI application entry point for the modular monolith.

All service routers are registered under a single FastAPI instance running on port 8000.
Service boundaries are enforced via Python module packages and dependency injection.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="TopInjector",
        description=(
            "SaaS dashboard for monitoring keyword positions and managing search traffic patterns across websites."
        ),
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",  # under /api so nginx routes it to the backend
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- Register service routers ----------------------------------------- #
    from services.analytics_service.routes import analytics as analytics_router
    from services.auth_service.routes import auth as auth_router
    from services.external_api_service.routes import external as external_router
    from services.notification_service.routes import (
        notifications as notification_router,
    )
    from services.project_service.routes import external_services as external_services_router
    from services.project_service.routes import integration_groups as integration_groups_router
    from services.project_service.routes import plans as plans_router
    from services.project_service.routes import projects as project_router
    from services.project_service.routes import referral as referral_router
    from services.project_service.routes import warmups as warmup_router
    from services.project_service.routes import whitelabel as whitelabel_router
    from services.project_service.routes import xmlstock_serp as xmlstock_serp_router
    from services.queue_service.routes import queue as queue_router
    from services.user_service.routes import users as user_router

    # Prefixes live here only; module routers declare paths relative to them.
    app.include_router(auth_router.router, prefix="/api/auth")
    app.include_router(user_router.router, prefix="/api/users")
    app.include_router(project_router.router, prefix="/api/projects")
    app.include_router(queue_router.router, prefix="/api/queue")
    app.include_router(analytics_router.router, prefix="/api/analytics")
    app.include_router(notification_router.router, prefix="/api/notifications")
    app.include_router(external_router.router, prefix="/api/external/v1")
    app.include_router(warmup_router.router, prefix="/api/warmups")
    app.include_router(plans_router.router, prefix="/api")
    app.include_router(external_services_router.router, prefix="/api/external-services")
    app.include_router(whitelabel_router.router, prefix="/api/whitelabel")
    app.include_router(integration_groups_router.router)
    app.include_router(referral_router.router)
    app.include_router(xmlstock_serp_router.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
