"""Warmup campaign routes — pre-heating search traffic patterns."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.jwt_utils import get_current_user
from shared.database.session import get_session
from services.auth_service.domain.models import User

router = APIRouter(tags=["warmups"])


@router.get("")
async def list_warmups(
    project_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List warmup campaigns for the authenticated user."""
    from services.project_service.domain.models import Project, WarmupCampaign

    stmt = select(WarmupCampaign).where(
        and_(
            WarmupCampaign.user_id == user.id,
        )
    )
    if project_id:
        # Verify project belongs to user
        proj_result = await session.execute(
            select(Project.id).where(
                and_(Project.id == UUID(project_id), Project.user_id == user.id)
            )
        )
        if not proj_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Project not found")
        stmt = stmt.where(WarmupCampaign.project_id == UUID(project_id))

    result = await session.execute(stmt.order_by(WarmupCampaign.created_at.desc()))
    warmups = result.scalars().all()

    return [
        {
            "id": str(w.id),
            "project_id": str(w.project_id) if w.project_id else None,
            "project_name": w.project_name or "",
            "name": w.name or "",
            "status": w.status or "draft",
            "clicks_per_hour": w.clicks_per_hour or 0,
            "total_target": w.total_target or 0,
            "completed_clicks": w.completed_clicks or 0,
            "start_time": w.start_time.isoformat() if w.start_time else None,
            "end_time": w.end_time.isoformat() if w.end_time else None,
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w in warmups
    ]


@router.post("")
async def create_warmup(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new warmup campaign."""
    from services.project_service.domain.models import Project, WarmupCampaign

    name = body.get("name", "Warmup Campaign")
    project_id_str = body.get("project_id")
    clicks_per_hour = body.get("clicks_per_hour", 10)
    total_target = body.get("total_target", 100)
    start_time_str = body.get("start_time")
    end_time_str = body.get("end_time")

    project_id: UUID | None = None
    project_name: str | None = None

    if project_id_str:
        proj_result = await session.execute(
            select(Project).where(
                and_(Project.id == UUID(project_id_str), Project.user_id == user.id)
            )
        )
        proj = proj_result.scalar_one_or_none()
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
        project_id = proj.id
        project_name = proj.name

    from datetime import datetime, timezone

    start_time: datetime | None = None
    end_time: datetime | None = None
    if start_time_str:
        start_time = datetime.fromisoformat(start_time_str)
    if end_time_str:
        end_time = datetime.fromisoformat(end_time_str)

    warmup = WarmupCampaign(
        id=UUID(int=0),  # placeholder
        user_id=user.id,
        project_id=project_id,
        project_name=project_name,
        name=name,
        status="draft",
        clicks_per_hour=clicks_per_hour,
        total_target=total_target,
        completed_clicks=0,
        start_time=start_time,
        end_time=end_time,
    )

    from uuid import uuid4
    warmup.id = uuid4()
    session.add(warmup)
    await session.commit()
    await session.refresh(warmup)

    return {
        "id": str(warmup.id),
        "project_id": str(warmup.project_id) if warmup.project_id else None,
        "project_name": warmup.project_name or "",
        "name": warmup.name,
        "status": warmup.status,
        "clicks_per_hour": warmup.clicks_per_hour,
        "total_target": warmup.total_target,
        "completed_clicks": warmup.completed_clicks,
        "start_time": warmup.start_time.isoformat() if warmup.start_time else None,
        "end_time": warmup.end_time.isoformat() if warmup.end_time else None,
        "created_at": warmup.created_at.isoformat() if warmup.created_at else None,
    }


@router.put("/{warmup_id}")
async def update_warmup(
    warmup_id: str,
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update a warmup campaign (name, status, clicks_per_hour, etc.)."""
    from services.project_service.domain.models import WarmupCampaign

    result = await session.execute(
        select(WarmupCampaign).where(
            and_(
                WarmupCampaign.id == UUID(warmup_id),
                WarmupCampaign.user_id == user.id,
            )
        )
    )
    w = result.scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="Warmup campaign not found")

    for key in ("name", "status", "clicks_per_hour", "total_target"):
        if key in body:
            setattr(w, key, body[key])

    await session.commit()
    await session.refresh(w)

    return {
        "id": str(w.id),
        "status": w.status,
        "name": w.name,
        "clicks_per_hour": w.clicks_per_hour,
        "total_target": w.total_target,
        "completed_clicks": w.completed_clicks,
    }


@router.delete("/{warmup_id}")
async def delete_warmup(
    warmup_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete a warmup campaign."""
    from services.project_service.domain.models import WarmupCampaign

    result = await session.execute(
        select(WarmupCampaign).where(
            and_(
                WarmupCampaign.id == UUID(warmup_id),
                WarmupCampaign.user_id == user.id,
            )
        )
    )
    w = result.scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="Warmup campaign not found")

    await session.delete(w)
    await session.commit()
    return {"deleted": True}


@router.post("/{warmup_id}/tick")
async def tick_warmup(
    warmup_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Tick a warmup campaign — records one completed click."""
    from services.project_service.domain.models import WarmupCampaign

    result = await session.execute(
        select(WarmupCampaign).where(
            and_(
                WarmupCampaign.id == UUID(warmup_id),
                WarmupCampaign.user_id == user.id,
            )
        )
    )
    w = result.scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="Warmup campaign not found")

    if w.status != "active":
        raise HTTPException(status_code=400, detail="Campaign is not active")

    w.completed_clicks = (w.completed_clicks or 0) + 1
    if w.completed_clicks >= (w.total_target or 0):
        w.status = "completed"

    await session.commit()
    await session.refresh(w)

    return {
        "id": str(w.id),
        "status": w.status,
        "completed_clicks": w.completed_clicks,
        "total_target": w.total_target,
        "progress_pct": round((w.completed_clicks / (w.total_target or 1)) * 100, 1),
    }
