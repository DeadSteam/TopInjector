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


@router.delete("/api-tokens/{token_id}")
async def delete_api_token(
    token_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete an API token. Requires valid JWT."""
    from services.project_service.domain.models import ProjectToken

    result = await session.execute(
        select(ProjectToken).where(
            ProjectToken.id == UUID(token_id),
            ProjectToken.user_id == user.id,
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    await session.delete(token)
    await session.commit()
    return {"deleted": True}


# --- User settings: messenger, external services, password ------------------ #


@router.get("/settings/messenger")
async def get_messenger_settings(
    user: User = Depends(get_current_user),
):
    """Get messenger integration settings (JSON)."""
    # Telegram webhook URL stored in user settings
    settings: dict = getattr(user, "messenger_settings", {}) or {}
    return {
        "telegram_webhook_url": settings.get("telegram_webhook_url", ""),
        "max_connector_id": settings.get("max_connector_id", ""),
    }


@router.post("/settings/messenger")
async def update_messenger_settings(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update messenger integration settings (JSON)."""
    from services.auth_service.domain.models import User as UserModel

    current = getattr(user, "messenger_settings", {}) or {}
    if "telegram_webhook_url" in body:
        current["telegram_webhook_url"] = body["telegram_webhook_url"]
    if "max_connector_id" in body:
        current["max_connector_id"] = body["max_connector_id"]
    setattr(user, "messenger_settings", current)
    # Update via SQLAlchemy directly since MessengerSettings may not be a model
    from sqlalchemy import select as sa_select
    q = await session.execute(sa_select(UserModel).where(UserModel.id == user.id))
    u = q.scalar_one_or_none()
    if u:
        u.messenger_settings = current  # type: ignore[attr-defined]
    await session.commit()
    await session.refresh(user)
    return {"updated": True, "settings": getattr(user, "messenger_settings", {})}


@router.get("/settings/external-services")
async def get_external_services(
    user: User = Depends(get_current_user),
):
    """Get external services configuration (XML River / XMLStock) as JSON."""
    settings: dict = getattr(user, "external_services", {}) or {}
    return {
        "xml_river": settings.get("xml_river"),
        "xml_stock": settings.get("xml_stock"),
    }


@router.post("/settings/external-services")
async def update_external_services(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update external services configuration (XML River / XMLStock)."""
    from sqlalchemy import select as sa_select
    from services.auth_service.domain.models import User as UserModel

    current = getattr(user, "external_services", {}) or {}
    if "xml_river" in body:
        current["xml_river"] = body["xml_river"]
    if "xml_stock" in body:
        current["xml_stock"] = body["xml_stock"]
    setattr(user, "external_services", current)
    q = await session.execute(sa_select(UserModel).where(UserModel.id == user.id))
    u = q.scalar_one_or_none()
    if u:
        u.external_services = current  # type: ignore[attr-defined]
    await session.commit()
    await session.refresh(user)
    return {"updated": True, "settings": getattr(user, "external_services", {})}


@router.post("/password")
async def change_password(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Change user password. Requires current_password + new_password."""
    from passlib.context import CryptContext

    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    current_pw = body.get("current_password", "")
    new_pw = body.get("new_password", "")

    if not current_pw or not new_pw:
        raise HTTPException(status_code=400, detail="current_password and new_password are required")
    if len(new_pw) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    if not pwd_ctx.verify(current_pw, user.hashed_password):  # type: ignore[attr-defined]
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.hashed_password = pwd_ctx.hash(new_pw)  # type: ignore[attr-defined]
    await session.commit()
    return {"updated": True}


# --- Avatar upload/delete --------------------------------------------------- #


@router.post("/avatar")
async def upload_avatar(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Upload avatar URL for the current user. Expects JSON body with 'avatar_url' field."""
    from sqlalchemy import select as sa_select

    if "avatar_url" not in body:
        raise HTTPException(status_code=400, detail="avatar_url is required")

    from services.auth_service.domain.models import User as UserModel
    result = await session.execute(sa_select(UserModel).where(UserModel.id == user.id))
    u = result.scalar_one_or_none()
    if u:
        u.avatar_url = body["avatar_url"]  # type: ignore[attr-defined]

    await session.commit()
    return {"updated": True, "avatar_url": body["avatar_url"]}


@router.delete("/avatar")
async def delete_avatar(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete avatar URL for the current user."""
    from sqlalchemy import select as sa_select

    from services.auth_service.domain.models import User as UserModel
    result = await session.execute(sa_select(UserModel).where(UserModel.id == user.id))
    u = result.scalar_one_or_none()
    if u:
        u.avatar_url = None  # type: ignore[attr-defined]

    await session.commit()
    return {"deleted": True}


@router.get("/avatar")
async def get_avatar(
    user: User = Depends(get_current_user),
):
    """Get current avatar URL."""
    av = getattr(user, "avatar_url", None)
    return {"avatar_url": av}
