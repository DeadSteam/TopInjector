"""Referral link management for users."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth_service.domain.models import User
from services.project_service.domain.models import ReferralLink
from shared.auth.jwt_utils import get_current_user
from shared.database.session import get_session

router = APIRouter(tags=["referral"])


@router.get("/referral/link")
async def get_referral_link(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get or create the user's referral link."""
    existing = (await session.execute(
        sa_select(ReferralLink).where(ReferralLink.user_id == user.id)
    )).scalar_one_or_none()
    if existing is not None:
        return {
            "id": str(existing.id),
            "code": existing.code,
            "link": f"/register?ref={existing.code}",
            "clicks": existing.clicks,
            "signups": existing.signups,
        }

    # Generate unique code
    import secrets as _secrets
    code = _secrets.token_urlsafe(8)[:12]
    referral = ReferralLink(
        id=uuid4(),
        user_id=user.id,
        code=code,
    )
    session.add(referral)
    await session.commit()
    await session.refresh(referral)
    return {
        "id": str(referral.id),
        "code": referral.code,
        "link": f"/register?ref={referral.code}",
        "clicks": referral.clicks,
        "signups": referral.signups,
    }


@router.post("/referral/link/click")
async def click_referral_link(
    code: str,
    session: AsyncSession = Depends(get_session),
):
    """Track a click on a referral link."""
    ref = (await session.execute(
        sa_select(ReferralLink).where(ReferralLink.code == code)
    )).scalar_one_or_none()
    if not ref:
        raise HTTPException(status_code=404, detail="Invalid referral code")
    ref.clicks += 1
    await session.commit()
    return {"clicks": ref.clicks}


@router.post("/referral/link/signup/{code}")
async def signup_with_referral(
    code: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Track a signup from a referral link — award bonus credits."""
    ref = (await session.execute(
        sa_select(ReferralLink).where(ReferralLink.code == code)
    )).scalar_one_or_none()
    if not ref:
        raise HTTPException(status_code=404, detail="Invalid referral code")

    ref.signups += 1

    # Award bonus credits to the referral source (not the signer-up)
    OWNER = await session.get(User, ref.user_id)
    if OWNER:
        OWNER.bonus_credits += 50000  # 500 RUB bonus
        await session.commit()
        await session.refresh(OWNER)

    return {"signups": ref.signups, "bonus_awarded": True}


@router.get("/referral/stats")
async def referral_stats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get referral stats for the user (if they were referred)."""
    ref_link = (await session.execute(
        sa_select(ReferralLink)
        .where(ReferralLink.user_id == user.id)
    )).scalar_one_or_none()

    # Check if user was referred (they have a referral source)
    return {
        "referred_by": ref_link.code if ref_link else None,
        "bonus_credits": user.bonus_credits,
    }
