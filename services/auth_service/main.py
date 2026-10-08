"""Auth service main entry point."""

from fastapi import APIRouter

router = APIRouter()

# Import routes to register handlers
from services.auth_service.routes.auth import router as auth_router  # noqa: F401

router.include_router(auth_router, prefix="/auth", tags=["auth"])
