"""White-label branding routes: the current user's settings, a DNS check, and public lookup by domain."""

import socket
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth_service.domain.models import User
from services.project_service.domain.whitelabel import MAX_BLURB_LEN, WhiteLabel
from shared.auth.jwt_utils import get_current_user
from shared.database.session import get_session
from shared.validation import ensure_safe_url

router = APIRouter(tags=["whitelabel"])

# Fields a user may set; asset keys hold a storage key or URL to an already-uploaded file.
_EDITABLE = {
    "domain", "platform_name", "accent_color", "description_md", "welcome_text_md", "website_url",
    "logo_light_key", "logo_dark_key", "favicon_key", "banner_catalog_key", "banner_homepage_key",
    "is_active",
}


def _json(wl: WhiteLabel) -> dict:
    return {
        "id": str(wl.id),
        "domain": wl.domain,
        "dns_status": wl.dns_status,
        "platform_name": wl.platform_name,
        "accent_color": wl.accent_color,
        "description_md": wl.description_md,
        "welcome_text_md": wl.welcome_text_md,
        "website_url": wl.website_url,
        "logo_light_key": wl.logo_light_key,
        "logo_dark_key": wl.logo_dark_key,
        "favicon_key": wl.favicon_key,
        "banner_catalog_key": wl.banner_catalog_key,
        "banner_homepage_key": wl.banner_homepage_key,
        "is_active": wl.is_active,
    }


async def _get_or_create(session: AsyncSession, user_id: UUID) -> WhiteLabel:
    wl = (await session.execute(select(WhiteLabel).where(WhiteLabel.user_id == user_id))).scalar_one_or_none()
    if wl is None:
        wl = WhiteLabel(user_id=user_id)
        session.add(wl)
        await session.commit()
        wl = (await session.execute(select(WhiteLabel).where(WhiteLabel.user_id == user_id))).scalar_one()
    return wl


@router.get("")
async def get_whitelabel(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Current user's branding settings (created with defaults on first read)."""
    return _json(await _get_or_create(session, user.id))


@router.put("")
async def update_whitelabel(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update branding. Changing the domain resets its DNS status to pending."""
    wl = await _get_or_create(session, user.id)

    unknown = sorted(set(body) - _EDITABLE)
    if unknown:
        raise HTTPException(status_code=422, detail=f"Field(s) can't be changed here: {', '.join(unknown)}")
    for field in ("description_md", "welcome_text_md"):
        if field in body and len(str(body[field] or "")) > MAX_BLURB_LEN:
            raise HTTPException(status_code=422, detail=f"{field} must be at most {MAX_BLURB_LEN} characters")
    if body.get("website_url"):
        ensure_safe_url(body["website_url"], "website_url")

    if "domain" in body and body["domain"] != wl.domain:
        wl.dns_status = "pending"  # re-verify after a domain change
    for field in _EDITABLE:
        if field in body:
            setattr(wl, field, body[field])

    await session.commit()
    await session.refresh(wl)
    return _json(wl)


@router.post("/check-dns")
async def check_dns(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Check whether the configured custom domain resolves; records verified/error."""
    wl = await _get_or_create(session, user.id)
    if not wl.domain:
        raise HTTPException(status_code=422, detail="No domain configured")
    try:
        socket.getaddrinfo(wl.domain, None)
        wl.dns_status = "verified"
    except OSError:
        wl.dns_status = "error"
    await session.commit()
    return {"domain": wl.domain, "dns_status": wl.dns_status}


@router.get("/public/{domain}")
async def public_branding(domain: str, session: AsyncSession = Depends(get_session)):
    """Public branding for a verified custom domain (used to theme the login page). No auth."""
    wl = (await session.execute(
        select(WhiteLabel).where(
            WhiteLabel.domain == domain,
            WhiteLabel.is_active == True,  # noqa: E712
            WhiteLabel.dns_status == "verified",
        )
    )).scalar_one_or_none()
    if wl is None:
        raise HTTPException(status_code=404, detail="No branding for this domain")
    return {
        "platform_name": wl.platform_name,
        "accent_color": wl.accent_color,
        "description_md": wl.description_md,
        "welcome_text_md": wl.welcome_text_md,
        "website_url": wl.website_url,
        "logo_light_key": wl.logo_light_key,
        "logo_dark_key": wl.logo_dark_key,
        "favicon_key": wl.favicon_key,
    }
