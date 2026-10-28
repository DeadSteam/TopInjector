"""Daily billing worker — deducts the plan's daily cost from each active user.

Priority of deduction: bonus_credits first, then prepay_per_click_cop.
Records a ``BalanceTransaction`` with type ``plan_deduction`` per project owned by the user
(aggregate daily cost = price_per_day / number_of_projects … or simply the full price_per_day
as the subscription charge; we record it once at the user level).

If bonus_credits cover part and prepay covers the rest, two transactions are recorded.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth_service.domain.models import User
from services.project_service.domain.models import BalanceTransaction, Plan, Project, UserPlan
from workers import app
from workers.db import run_with_session


async def _charge_user(session: AsyncSession, user: User, daily_cost_kop: int, project_id: UUID) -> list[BalanceTransaction]:
    """Deduct *daily_cost_kop* from the user's balances (bonus first, then prepay).

    Records a ``BalanceTransaction`` attached to *project_id*.
    Returns a list of created ``BalanceTransaction`` records.
    """
    txns: list[BalanceTransaction] = []
    remaining = daily_cost_kop

    # 1) consume bonus_credits
    if user.bonus_credits > 0 and remaining > 0:
        bonus_used = min(user.bonus_credits, remaining)
        user.bonus_credits -= bonus_used
        remaining -= bonus_used
        txns.append(BalanceTransaction(
            id=uuid4(),
            project_id=project_id,
            amount=-bonus_used,
            description=f"Plan deduction from bonus credits ({user.display_name or user.email})",
            type="plan_deduction",
        ))

    # 2) consume prepay_per_click_cop
    if user.prepay_per_click_cop > 0 and remaining > 0:
        prepay_used = min(user.prepay_per_click_cop, remaining)
        user.prepay_per_click_cop -= prepay_used
        remaining -= prepay_used
        txns.append(BalanceTransaction(
            id=uuid4(),
            project_id=project_id,
            amount=-prepay_used,
            description=f"Plan deduction from prepay ({user.display_name or user.email})",
            type="plan_deduction",
        ))

    if remaining > 0:
        # Insufficient funds — log but don't fail
        txns.append(BalanceTransaction(
            id=uuid4(),
            project_id=project_id,
            amount=0,
            description=f"Plan deduction insufficient: need {remaining} more kopeks",
            type="plan_deduction",
        ))

    await session.commit()
    return txns


async def daily_billing(session: AsyncSession, now: datetime | None = None) -> dict:
    """Run one daily billing cycle. Returns summary counts."""
    now = now or datetime.now(timezone.utc)

    # Get all active user plans with paid tiers (exclude "start" free tier)
    active_plans = (await session.execute(
        select(Plan).where(Plan.slug != "start", Plan.is_active.is_(True))
    )).scalars().all()
    plan_map = {p.slug: p for p in active_plans}

    active_user_plans = (await session.execute(
        select(UserPlan)
        .join(Plan, UserPlan.plan_id == Plan.id)
        .where(UserPlan.is_active.is_(True), Plan.slug != "start")
    )).scalars().all()

    charged = 0
    failed = 0
    skipped = 0

    for up in active_user_plans:
        user = await session.get(User, up.user_id)
        if not user or not user.is_active:
            skipped += 1
            continue

        plan = up.plan
        daily_cost = plan.price_per_day

        # Prorate for partial month if period_start is mid-month
        if up.period_start:
            from datetime import date
            period_start_date = up.period_start.date()
            today = now.date()
            # Simple daily proration: full cost per day
            days_in_period = (today - period_start_date).days + 1
            if days_in_period <= 0:
                skipped += 1
                continue

        # Pick first active project for the transaction FK (or user's first project)
        projects = (await session.execute(
            select(Project).where(Project.user_id == user.id, Project.is_active.is_(True)).limit(1)
        )).scalars().all()
        target_project = projects[0] if projects else None
        if not target_project:
            skipped += 1
            continue

        try:
            await _charge_user(session, user, daily_cost, target_project.id)
            charged += 1
        except Exception:
            failed += 1
            await session.rollback()

    return {"charged": charged, "failed": failed, "skipped": skipped}


@app.task(name="workers.daily_billing.run_daily_billing")
def run_daily_billing():
    """Beat entry point — runs once per day (typically at midnight UTC)."""
    result = run_with_session(daily_billing)
    return result or {"charged": 0, "failed": 0, "skipped": 0}
