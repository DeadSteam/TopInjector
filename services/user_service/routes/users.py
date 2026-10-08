"""User service routes — profile management, API tokens."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.jwt_utils import get_current_user
from shared.database.session import get_session
from services.auth_service.domain.models import User

router = APIRouter(tags=["users"])


@router.get("/profile")
async def get_profile(
    user: User = Depends(get_current_user),
):
    """Get current user profile. Requires valid JWT."""
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name or "",
        "balance": 0,
        "plan": "free",
        "is_active": bool(user.is_active),
    }


@router.put("/profile")
async def update_profile(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update current user profile. Requires valid JWT."""
    for key in ("display_name",):
        if key in body:
            setattr(user, key, body[key])

    await session.commit()
    await session.refresh(user)
    return {"id": str(user.id), "display_name": user.display_name, "updated": True}


@router.get("/api-tokens")
async def list_api_tokens(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List API tokens for the authenticated user. Requires valid JWT."""
    from services.project_service.domain.models import ProjectToken

    result = await session.execute(select(ProjectToken).where(ProjectToken.user_id == user.id))
    tokens = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "name": t.name or "",
            "token": t.token_string[:8] + "..." if len(t.token_string) > 8 else "***",
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tokens
    ]


@router.post("/api-tokens")
async def create_api_token(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new API token for the authenticated user. Requires valid JWT."""
    import secrets

    from services.project_service.domain.models import ProjectToken

    name = body.get("name", "API Token")
    token_string = f"tl_{secrets.token_urlsafe(32)}"
    project_token = ProjectToken(
        id=UUID(int=0),  # placeholder — real UUID created via uuid4 below
        user_id=user.id,
        name=name,
        token_string=token_string,
    )

    from uuid import uuid4
    project_token.id = uuid4()
    session.add(project_token)
    await session.commit()
    await session.refresh(project_token)

    return {
        "id": str(project_token.id),
        "name": project_token.name,
        "token": project_token.token_string,
        "created_at": project_token.created_at.isoformat() if project_token.created_at else None,
    }
