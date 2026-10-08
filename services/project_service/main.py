"""Project service main entry point."""
from fastapi import APIRouter

router = APIRouter()
from services.project_service.routes.projects import router as projects_router  # noqa: F401

router.include_router(projects_router, prefix="/projects", tags=["projects"])
