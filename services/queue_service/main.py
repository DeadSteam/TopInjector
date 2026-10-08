"""Queue service main entry point."""
from fastapi import APIRouter

router = APIRouter()
from services.queue_service.routes.queue import router as queue_router  # noqa: F401

router.include_router(queue_router, prefix="/queue", tags=["queue"])
