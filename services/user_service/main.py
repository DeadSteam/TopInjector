"""User service main entry point."""
from fastapi import APIRouter

router = APIRouter()
from services.user_service.routes.users import router as users_router  # noqa: F401, E402

router.include_router(users_router, prefix="/users", tags=["users"])
