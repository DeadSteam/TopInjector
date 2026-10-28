"""User service routes — profile management, API tokens."""

from uuid import UUID

import bcrypt
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.access import check_project_access
from shared.auth.jwt_utils import get_current_user
from shared.config import settings
from shared.database.session import get_session
from shared.validation import require_fields, validate_password
from services.auth_service.domain.models import User

router = APIRouter(tags=["users"])


@router.get("/profile")
async def get_profile(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Current user's profile; balance is the sum of the user's own project balances, in rubles."""
    from services.project_service.domain.models import Project

    credits = (await session.execute(
        select(func.coalesce(func.sum(Project.balance_credits), 0)).where(Project.user_id == user.id)
    )).scalar_one()
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name or "",
        "balance": round(credits / 100, 2),
        "is_admin": user.email.lower() in settings.admin_email_set,
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

    from services.project_service.domain.models import Project

    result = await session.execute(
        select(ProjectToken, Project.name)
        .outerjoin(Project, Project.id == ProjectToken.project_id)
        .where(ProjectToken.user_id == user.id)
        .order_by(ProjectToken.created_at)
    )
    return [
        {
            "id": str(t.id),
            "name": t.name or "",
            "token": t.token_string[:8] + "..." if len(t.token_string) > 8 else "***",
            "project_id": str(t.project_id) if t.project_id else None,
            "project_name": project_name,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t, project_name in result.all()
    ]


@router.post("/api-tokens")
async def create_api_token(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create an external-API token (X-Auth-Token) bound to one of the user's projects."""
    import secrets
    from uuid import uuid4

    from services.project_service.domain.models import ProjectToken

    # The external API resolves the project from the token, so a token must name one the user owns.
    require_fields(body, "project_id")
    project = await check_project_access(session, body["project_id"], user.id, owner_only=True)
    existing = await session.execute(
        select(ProjectToken.id).where(ProjectToken.user_id == user.id, ProjectToken.project_id == project.id)
    )
    if existing.first():
        raise HTTPException(status_code=409, detail="У этого проекта уже есть токен — удалите старый, чтобы выпустить новый")

    project_token = ProjectToken(
        id=uuid4(),
        user_id=user.id,
        project_id=project.id,
        name=body.get("name") or "API Token",
        token_string=f"tl_{secrets.token_urlsafe(32)}",
    )
    session.add(project_token)
    await session.commit()
    await session.refresh(project_token)

    return {
        "id": str(project_token.id),
        "name": project_token.name,
        "token": project_token.token_string,
        "project_id": str(project.id),
        "project_name": project.name,
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
    current = dict(user.messenger_settings or {})
    for key in ("telegram_webhook_url", "max_connector_id"):
        if key in body:
            current[key] = body[key]
    user.messenger_settings = current
    await session.commit()
    return {"updated": True, "settings": current}


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
    current = dict(user.external_services or {})
    for key in ("xml_river", "xml_stock"):
        if key in body:
            current[key] = body[key]
    user.external_services = current
    await session.commit()
    return {"updated": True, "settings": current}


@router.post("/password")
async def change_password(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Change user password. Requires current_password + new_password."""
    current_pw = body.get("current_password", "")
    new_pw = body.get("new_password", "")

    if not current_pw or not new_pw:
        raise HTTPException(status_code=400, detail="current_password and new_password are required")
    validate_password(new_pw)

    try:
        current_ok = bcrypt.checkpw(current_pw.encode("utf-8"), user.password_hash.encode("utf-8"))
    except ValueError:
        current_ok = False
    if not current_ok:
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.password_hash = bcrypt.hashpw(new_pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
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


# --- Stop words management -------------------------------------------------- #


async def _save_stop_words(user: User, session: AsyncSession, words: list[str]) -> None:
    """Persist stop words inside messenger_settings (assign a new dict so the JSON change is tracked)."""
    user.messenger_settings = {**(user.messenger_settings or {}), "stop_words": words}
    await session.commit()


@router.get("/settings/stop-words")
async def get_stop_words(
    user: User = Depends(get_current_user),
):
    """Get user's stop words list (JSONB in user settings)."""
    settings: dict = getattr(user, "messenger_settings", {}) or {}
    return {"stop_words": settings.get("stop_words", [])}


@router.post("/settings/stop-words")
async def update_stop_words(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update user's stop words list. Accepts {stop_words: [...]}."""
    words = body.get("stop_words", [])
    # Deduplicate and lowercase
    stop_words = list(set(w.strip().lower() for w in words if w.strip()))
    await _save_stop_words(user, session, stop_words)
    return {"updated": True, "stop_words": stop_words}


@router.post("/settings/stop-words/add")
async def add_stop_word(
    word: str = Body(..., embed=True),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Add a single stop word."""
    w = word.strip().lower()
    if not w:
        raise HTTPException(status_code=400, detail="Stop word cannot be empty")

    words = list((user.messenger_settings or {}).get("stop_words", []))
    if w in words:
        return {"added": False, "duplicate": True, "stop_words": words}
    words.append(w)
    await _save_stop_words(user, session, words)
    return {"added": True, "stop_words": words}


@router.delete("/settings/stop-words/{word}")
async def remove_stop_word(
    word: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Remove a single stop word."""
    w = word.strip().lower()
    words = [x for x in (user.messenger_settings or {}).get("stop_words", []) if x != w]
    await _save_stop_words(user, session, words)
    return {"stop_words": words}


# --- Prepay per click -------------------------------------------------------- #


@router.get("/settings/prepay-per-click")
async def get_prepay_per_click(
    user: User = Depends(get_current_user),
):
    """Get the user's prepay per click setting in kopeks."""
    return {"prepay_per_click_cop": user.prepay_per_click_cop}


@router.post("/settings/prepay-per-click")
async def update_prepay_per_click(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update the user's prepay per click setting (in kopeks / ruble * 100)."""
    cop = body.get("prepay_per_click_cop", 0)
    try:
        cop = int(cop)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="prepay_per_click_cop must be an integer")
    if cop < 0:
        raise HTTPException(status_code=422, detail="prepay_per_click_cop cannot be negative")
    user.prepay_per_click_cop = cop  # type: ignore[attr-defined]
    await session.commit()
    return {"updated": True, "prepay_per_click_cop": user.prepay_per_click_cop}
