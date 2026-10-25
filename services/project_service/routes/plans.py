"""Subscription plan routes: public catalogue, current status, and switching plan.

Pure subscription management — seat/project limits and price only, no traffic metering
and no balance movement on switch.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth_service.domain.models import User
from services.project_service.domain.models import Project
from services.project_service.domain.plans import Plan, UserPlan
from shared.auth.jwt_utils import get_current_user
from shared.database.session import get_session

router = APIRouter(tags=["plans"])

# Fallback catalogue used to seed an empty table on first read (app tests build tables from models,
# so the migration seed isn't present; a real deployment is already seeded by migration 0015).
_DEFAULT_PLANS = [
    ("start", "Start", 0, 0, 5, 1),
    ("lite", "Lite", 10000, 300000, 20, 10),
    ("plus", "Plus", 16000, 480000, 50, 25),
    ("pro", "Pro", 33000, 990000, 100, 75),
    ("ultra", "Ultra", 50000, 1500000, 200, 150),
    ("max", "Max", 85000, 2550000, 500, 500),
]


async def _ensure_plans_seeded(session: AsyncSession) -> None:
    if (await session.execute(select(func.count()).select_from(Plan))).scalar():
        return
    for slug, name, ppd, ppm, mu, mp in _DEFAULT_PLANS:
        session.add(Plan(
            slug=slug, display_name=name, is_active=True,
            price_per_day=ppd, price_per_month=ppm, max_users=mu, max_projects=mp,
        ))
    await session.commit()


def _plan_json(plan: Plan) -> dict:
    return {
        "id": str(plan.id),
        "slug": plan.slug,
        "display_name": plan.display_name,
        "is_active": plan.is_active,
        "price_per_day": plan.price_per_day,
        "price_per_month": plan.price_per_month,
        "max_users": plan.max_users,
        "max_projects": plan.max_projects,
    }


async def _get_or_create_user_plan(session: AsyncSession, user_id: UUID) -> UserPlan:
    """Return the user's plan, assigning Start the first time it's needed."""
    await _ensure_plans_seeded(session)
    up = (await session.execute(select(UserPlan).where(UserPlan.user_id == user_id))).scalar_one_or_none()
    if up is not None:
        return up
    start = (await session.execute(select(Plan).where(Plan.slug == "start"))).scalar_one()
    up = UserPlan(user_id=user_id, plan_id=start.id, is_active=True)
    session.add(up)
    await session.commit()
    return (await session.execute(select(UserPlan).where(UserPlan.user_id == user_id))).scalar_one()


@router.get("/plans")
async def list_plans(session: AsyncSession = Depends(get_session)):
    """Public catalogue of active plans."""
    await _ensure_plans_seeded(session)
    plans = (await session.execute(
        select(Plan).where(Plan.is_active == True).order_by(Plan.price_per_day)  # noqa: E712
    )).scalars().all()
    return {"plans": [_plan_json(p) for p in plans]}


@router.get("/plan/status")
async def plan_status(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Current user's plan, its limits, and current usage against them."""
    up = await _get_or_create_user_plan(session, user.id)
    plan = (await session.execute(select(Plan).where(Plan.id == up.plan_id))).scalar_one()
    project_count = (await session.execute(
        select(func.count()).select_from(Project).where(Project.user_id == user.id)
    )).scalar() or 0
    return {
        "plan": _plan_json(plan),
        "limits": {"max_users": plan.max_users, "max_projects": plan.max_projects},
        "usage": {"projects": project_count},
        "period_start": up.period_start.isoformat() if up.period_start else None,
        "period_end": up.period_end.isoformat() if up.period_end else None,
    }


@router.put("/plan")
async def switch_plan(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Switch the current user to another plan by slug or id (no balance change)."""
    await _ensure_plans_seeded(session)
    slug = body.get("slug")
    plan_id = body.get("plan_id")
    if slug:
        target = (await session.execute(select(Plan).where(Plan.slug == slug))).scalar_one_or_none()
    elif plan_id:
        try:
            target = await session.get(Plan, UUID(str(plan_id)))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid plan_id")
    else:
        raise HTTPException(status_code=422, detail="Required field(s): slug or plan_id")
    if target is None or not target.is_active:
        raise HTTPException(status_code=404, detail="Plan not found")

    up = await _get_or_create_user_plan(session, user.id)
    up.plan_id = target.id
    await session.commit()
    return {"switched": True, "plan": _plan_json(target)}
