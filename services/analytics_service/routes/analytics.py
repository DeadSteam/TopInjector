"""Analytics routes. Base URL prefix handled by main.py."""

from uuid import UUID

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.session import get_session
from services.queue_service.domain.models import QueueTask

router = APIRouter(tags=["analytics"])


def _parse_pid(project_id: str) -> UUID | None:
    """Parse project_id query param to UUID; returns None for empty string."""
    if not project_id:
        return None
    try:
        return UUID(project_id)
    except ValueError:
        return None


@router.get("/summary")
async def get_summary(
    project_id: str = Query(default=""),
    start_date: str = Query(default=""),
    end_date: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
):
    """Return aggregate stats: total clicks, avg position, geo distribution."""
    # Get user projects count (any project for now; scoped by auth later)
    result = await session.execute(
        select(func.count(QueueTask.id))
    )
    total_tasks = result.scalar() or 0

    completed_result = await session.execute(
        select(func.count(QueueTask.id))
        .where(QueueTask.status == "completed")
    )
    completed_count = completed_result.scalar() or 0

    # Completed rate (0-1)
    completed_rate = completed_count / total_tasks if total_tasks > 0 else 0.0

    return {
        "project_id": project_id or "",
        "total_clicks": total_tasks,
        "completed_rate": round(completed_rate, 4),
        "avg_position": None,
        "geo_distribution": {},
        "date_range": {"start": start_date or "", "end": end_date or ""},
    }


@router.get("/positions")
async def get_positions(
    project_id: str = Query(default=""),
    query_text: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
):
    """Return position history for queries."""
    return {
        "project_id": project_id or "",
        "query_text": query_text or "",
        "history": [],
    }


@router.get("/clicks")
async def get_clicks(
    project_id: str = Query(default=""),
    start_date: str = Query(default=""),
    end_date: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
):
    """Return click timeline data for charts with optional date range filter."""
    pid = _parse_pid(project_id)
    where_conditions = [QueueTask.status == "completed"]
    if pid:
        where_conditions.append(QueueTask.project_id == pid)
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
            where_conditions.append(QueueTask.created_at >= sd)
        except (ValueError, TypeError):
            pass
    if end_date:
        try:
            ed = (datetime.fromisoformat(end_date) + __import__('datetime').timedelta(days=1)).replace(tzinfo=timezone.utc)
            where_conditions.append(QueueTask.created_at < ed)
        except (ValueError, TypeError):
            pass

    result = await session.execute(
        select(QueueTask.created_at, func.count(QueueTask.id))
        .where(*where_conditions)
        .group_by(QueueTask.created_at)
        .order_by(QueueTask.created_at)
    )

    timeline = [
        {"date": row[0].isoformat() if row[0] else "", "count": row[1]}
        for row in result.all()
    ]

    return {
        "project_id": project_id or "",
        "timeline": timeline,
    }


@router.get("/tracking/positions")
async def get_tracking_positions(
    project_id: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
):
    """Return detailed position tracking history with dates for chart rendering."""
    pid = _parse_pid(project_id)
    if not pid:
        return {
            "project_id": project_id or "",
            "tracking": [],
            "summary": {"best_position": None, "avg_position": None, "total_records": 0},
        }

    result = await session.execute(
        select(QueueTask.position, QueueTask.created_at)
        .where(
            QueueTask.project_id == pid,
            QueueTask.status == "completed",
            QueueTask.position.isnot(None),
        )
        .order_by(QueueTask.created_at)
    )

    tracking = [
        {
            "position": row[0],
            "date": row[1].isoformat() if row[1] else None,
        }
        for row in result.all()
    ]

    # Summary stats
    pos_only = [t["position"] for t in tracking]
    summary: dict = {
        "best_position": min(pos_only) if pos_only else None,
        "avg_position": round(sum(pos_only) / len(pos_only), 2) if pos_only else None,
        "total_records": len(tracking),
    }

    return {
        "project_id": project_id or "",
        "tracking": tracking,
        "summary": summary,
    }


@router.get("/top-ranges")
async def get_top_ranges(
    project_id: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
):
    """Return click distribution by TOP position ranges and avg position per range."""
    pid = _parse_pid(project_id)

    # Build WHERE clause
    where_conditions = [QueueTask.status == "completed"]
    if pid:
        where_conditions.append(QueueTask.project_id == pid)

    # Query completed tasks with positions, grouped into TOP ranges
    from sqlalchemy import literal_column

    range_label = case(
        (QueueTask.position <= 3, "1–3 (Топ-3)"),
        (QueueTask.position <= 5, "4–5"),
        (QueueTask.position <= 10, "6–10"),
        (QueueTask.position <= 20, "11–20"),
        (QueueTask.position <= 50, "21–50"),
        else_=">50",
    )

    result = await session.execute(
        select(range_label.label("label"),
               func.count(QueueTask.id).label("clicks"),
               func.avg(QueueTask.position).label("avg_pos"))
        .where(*where_conditions)
        .where(QueueTask.position.isnot(None))
        .group_by(range_label)
        .order_by(func.min(QueueTask.position))
    )

    rows = result.all()
    ranges = [
        {
            "label": row[0],
            "clicks": row[1] or 0,
            "avg_position": round(float(row[2]), 2) if row[2] is not None else None,
        }
        for row in rows
    ]

    # Ensure order from highest to lowest range for display
    range_order = ["1–3 (Топ-3)", "4–5", "6–10", "11–20", "21–50", ">50"]
    ranges.sort(key=lambda r: range_order.index(r["label"]) if r["label"] in range_order else 99)

    total_clicks = sum(r["clicks"] for r in ranges)
    overall_avg = sum(
        r["avg_position"] * r["clicks"] for r in ranges if r["avg_position"] is not None
    ) / total_clicks if total_clicks > 0 else None

    return {
        "project_id": project_id or "",
        "total_clicks": total_clicks,
        "ranges": ranges,
        "overall_avg_position": round(overall_avg, 2) if overall_avg is not None else None,
    }
