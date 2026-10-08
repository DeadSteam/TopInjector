"""Notification service main entry point."""
from fastapi import APIRouter

router = APIRouter()
from services.notification_service.routes.notifications import router as notif_router  # noqa: F401

router.include_router(notif_router, prefix="/notifications", tags=["notifications"])
