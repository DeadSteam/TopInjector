"""User service routes — profile management, API tokens."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session

router = APIRouter(tags=["users"])


@router.get("/profile")
async def get_profile(
    session: AsyncSession = Depends(get_session),
):
    """Get current user profile."""
    return {
        "id": "user-1",
        "email": "user@example.com",
        "display_name": "User",
        "balance": 0,
        "plan": "free",
        "is_active": True,
    }


@router.put("/profile")
async def update_profile(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Update user profile."""
    return {"id": "user-1", **body}


@router.get("/api-tokens")
async def list_api_tokens(
    session: AsyncSession = Depends(get_session),
):
    """List API tokens for the user."""
    return [{"id": "token-1", "name": "Main", "created_at": "2024-01-01T00:00:00Z"}]


@router.post("/api-tokens")
async def create_api_token(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Create a new API token (for external API access)."""
    import secrets

    return {
        "id": "token-new",
        "name": body.get("name", "New Token"),
        "token": f"tl_{secrets.token_urlsafe(32)}",
    }
