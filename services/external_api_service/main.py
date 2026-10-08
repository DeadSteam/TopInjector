"""External API service main entry point."""
from fastapi import APIRouter

router = APIRouter()
from services.external_api_service.routes.external import router as external_router  # noqa: F401

router.include_router(external_router, prefix="/external", tags=["external-api"])
