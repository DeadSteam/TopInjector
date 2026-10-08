"""Analytics service main entry point."""
from fastapi import APIRouter

router = APIRouter()
from services.analytics_service.routes.analytics import router as analytics_router  # noqa: F401

router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
