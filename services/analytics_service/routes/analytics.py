"""Analytics routes. Base URL prefix handled by main.py."""

from uuid import UUID

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.access import accessible_project_ids, request_user_id
from shared.database.session import get_session
from services.queue_service.domain.models import QueueTask

# Every route requires auth and only counts tasks of projects the caller may access.
router = APIRouter(tags=["analytics"], dependencies=[Depends(request_user_id)])


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
    suggestion_mode: str | None = Query(default=None),
    position_threshold: int | None = Query(default=None, ge=1, le=200),
    user_id: UUID = Depends(request_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Aggregate stats: total_clicks (completed tasks), avg_position (over clicks with a reported position)
    and completed_rate (completed / finished)."""
    from services.project_service.domain.models import Query as _QueryModel

    pid = _parse_pid(project_id)
    scope = [QueueTask.project_id.in_(accessible_project_ids(user_id))]  # projects + period
    if pid:
        scope.append(QueueTask.project_id == pid)
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
            scope.append(QueueTask.created_at >= sd)
        except (ValueError, TypeError):
            pass
    if end_date:
        try:
            ed = (datetime.fromisoformat(end_date) + __import__('datetime').timedelta(days=1)).replace(tzinfo=timezone.utc)
            scope.append(QueueTask.created_at < ed)
        except (ValueError, TypeError):
            pass
    where_conditions = [QueueTask.status == "completed", *scope]
    if position_threshold is not None and position_threshold > 0:
        where_conditions.append(QueueTask.position.isnot(None))
        where_conditions.append(QueueTask.position > position_threshold)

    # suggestion_mode requires joining queries — fast path without filter
    if suggestion_mode and suggestion_mode != "all":
        # Fetch completed task IDs with query_ids to filter by suggestion status
        result = await session.execute(
            select(QueueTask.id, QueueTask.query_id)
            .where(*where_conditions)
        )
        rows = result.all()

        # Build a set of allowed task IDs after filtering suggestions
        allowed_ids: set[int] = set()
        for row in rows:
            if row.query_id:
                q_row = await session.execute(
                    select(_QueryModel.query_modifications).where(_QueryModel.id == row.query_id)
                )
                mods = q_row.scalar_one_or_none() or {}
                has_suggestions = bool(mods.get("has_suggestions") or mods.get("with_suggestions"))
                if suggestion_mode == "with" and not has_suggestions:
                    continue
                if suggestion_mode == "without" and has_suggestions:
                    continue
            allowed_ids.add(row.id)

        where_conditions.append(QueueTask.id.in_(allowed_ids))

    # Total completed clicks and their average position (respects all filters)
    completed_count, avg_position = (await session.execute(
        select(func.count(QueueTask.id), func.avg(QueueTask.position)).where(*where_conditions)
    )).one()

    # Share of finished tasks (completed or not found) where the agent found the site
    outcomes = dict((await session.execute(
        select(QueueTask.status, func.count())
        .where(*scope, QueueTask.status.in_(["completed", "not_found"]))
        .group_by(QueueTask.status)
    )).all())
    finished = outcomes.get("completed", 0) + outcomes.get("not_found", 0)

    return {
        "project_id": project_id or "",
        "total_clicks": completed_count,
        "completed_clicks": completed_count,
        "avg_position": round(float(avg_position), 2) if avg_position is not None else None,
        "completed_rate": round(outcomes.get("completed", 0) / finished, 4) if finished else None,
        "geo_distribution": {},
        "date_range": {"start": start_date or "", "end": end_date or ""},
    }


@router.get("/positions")
async def get_positions(
    project_id: str = Query(default=""),
    query_text: str = Query(default=""),
    user_id: UUID = Depends(request_user_id),
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
    suggestion_mode: str | None = Query(default=None),
    position_threshold: int | None = Query(default=None, ge=1, le=200),
    user_id: UUID = Depends(request_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Return click timeline data for charts with optional date range and filters."""
    from services.project_service.domain.models import Query as _QueryModel

    pid = _parse_pid(project_id)
    where_conditions = [
        QueueTask.status == "completed",
        QueueTask.project_id.in_(accessible_project_ids(user_id)),
    ]
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
        select(QueueTask.id, QueueTask.query_id, QueueTask.created_at)
        .where(*where_conditions)
        .order_by(QueueTask.created_at)
    )
    rows = result.all()

    # Client-side suggestion_mode filter (requires looking up query query_modifications)
    if suggestion_mode and suggestion_mode != "all":
        filtered_rows = []
        for row in rows:
            if row.query_id:
                q_row = await session.execute(
                    select(_QueryModel.query_modifications).where(_QueryModel.id == row.query_id)
                )
                mods = q_row.scalar_one_or_none() or {}
                has_suggestions = bool(mods.get("has_suggestions") or mods.get("with_suggestions"))
                if suggestion_mode == "without" and has_suggestions:
                    continue
                if suggestion_mode == "with" and not has_suggestions:
                    continue
            # query_id is NULL => no associated query, always included
            filtered_rows.append(row)
        rows = filtered_rows

    # Apply position_threshold filter: only keep tasks where position > threshold
    if position_threshold is not None and position_threshold > 0:
        task_ids_with_pos = set()
        result2 = await session.execute(
            select(QueueTask.id, QueueTask.position)
            .where(QueueTask.id.in_([r.id for r in rows]))
            .where(QueueTask.position.isnot(None))
        )
        pos_map: dict[int, int] = {}
        for r2 in result2.all():
            pos_map[r2.id] = r2[1]
        filtered_rows2 = [r for r in rows if pos_map.get(r.id, 0) > position_threshold]
        rows = filtered_rows2

    # Re-aggregate by date from filtered results
    from collections import Counter
    timeline_map: dict[str, int] = {}
    for row in rows:
        if row.created_at:
            date_str = row.created_at.strftime("%Y-%m-%d")
            timeline_map[date_str] = timeline_map.get(date_str, 0) + 1
    timeline = [{"date": d, "count": c} for d, c in sorted(timeline_map.items())]

    return {
        "project_id": project_id or "",
        "timeline": timeline,
    }


@router.get("/tracking/positions")
async def get_tracking_positions(
    project_id: str = Query(default=""),
    user_id: UUID = Depends(request_user_id),
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
            QueueTask.project_id.in_(accessible_project_ids(user_id)),
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
    start_date: str = Query(default=""),
    end_date: str = Query(default=""),
    suggestion_mode: str | None = Query(default=None),
    position_threshold: int | None = Query(default=None, ge=1, le=200),
    user_id: UUID = Depends(request_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Return click distribution by TOP position ranges and avg position per range.

    no_position_clicks: completed clicks for which the agent reported no position.
    """
    from services.project_service.domain.models import Query as _QueryModel

    pid = _parse_pid(project_id)

    # Build WHERE clause
    where_conditions = [
        QueueTask.status == "completed",
        QueueTask.project_id.in_(accessible_project_ids(user_id)),
    ]
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

    # When suggestion_mode is set, we need to filter by query info — fetch first
    range_label = case(
        (QueueTask.position <= 3, "1–3 (Топ-3)"),
        (QueueTask.position <= 5, "4–5"),
        (QueueTask.position <= 10, "6–10"),
        (QueueTask.position <= 20, "11–20"),
        (QueueTask.position <= 50, "21–50"),
        else_=">50",
    )

    if suggestion_mode and suggestion_mode != "all":
        # Fetch tasks with position info and query_id for filtering
        result = await session.execute(
            select(QueueTask.id, QueueTask.query_id, QueueTask.position)
            .where(*where_conditions)
        )
        rows = result.all()

        filtered = []
        for row in rows:
            if row.query_id:
                q_row = await session.execute(
                    select(_QueryModel.query_modifications).where(_QueryModel.id == row.query_id)
                )
                mods = q_row.scalar_one_or_none() or {}
                has_suggestions = bool(mods.get("has_suggestions") or mods.get("with_suggestions"))
                if suggestion_mode == "without" and has_suggestions:
                    continue
                if suggestion_mode == "with" and not has_suggestions:
                    continue
            filtered.append(row)
        rows = filtered
        no_position_clicks = sum(1 for r in rows if r.position is None)

        # Apply position_threshold: keep only positions > threshold
        if position_threshold is not None and position_threshold > 0:
            rows = [r for r in rows if r.position is not None and r.position > position_threshold]

        # Aggregate manually from filtered results (after position_threshold was applied)
        range_agg: dict[str, list[int]] = {}
        for row in rows:
            pos = row.position
            if pos is None:
                continue
            label = (
                "1–3 (Топ-3)" if pos <= 3
                else "4–5" if pos <= 5
                else "6–10" if pos <= 10
                else "11–20" if pos <= 20
                else "21–50" if pos <= 50
                else ">50"
            )
            range_agg.setdefault(label, []).append(pos)

        ranges = []
        total_clicks = 0
        weighted_pos_sum = 0.0
        for label in ["1–3 (Топ-3)", "4–5", "6–10", "11–20", "21–50", ">50"]:
            positions = range_agg.get(label, [])
            if not positions:
                continue
            clicks = len(positions)
            avg_pos = sum(positions) / clicks
            ranges.append({
                "label": label,
                "clicks": clicks,
                "avg_position": round(avg_pos, 2),
            })
            total_clicks += clicks
            weighted_pos_sum += avg_pos * clicks

        overall_avg = weighted_pos_sum / total_clicks if total_clicks > 0 else None
    else:
        # Fast SQL path without suggestion_mode filter
        sql_where = list(where_conditions)
        sql_where.append(QueueTask.position.isnot(None))
        if position_threshold is not None and position_threshold > 0:
            sql_where.append(QueueTask.position > position_threshold)

        result = await session.execute(
            select(range_label.label("label"),
                   func.count(QueueTask.id).label("clicks"),
                   func.avg(QueueTask.position).label("avg_pos"))
            .where(*sql_where)
            .group_by(range_label)
            .order_by(func.min(QueueTask.position))
        )

        rows = result.all()
        no_position_clicks = (await session.execute(
            select(func.count(QueueTask.id)).where(*where_conditions, QueueTask.position.is_(None))
        )).scalar() or 0
        ranges = [
            {
                "label": row[0],
                "clicks": row[1] or 0,
                "avg_position": round(float(row[2]), 2) if row[2] is not None else None,
            }
            for row in rows
        ]

        total_clicks = sum(r["clicks"] for r in ranges)
        overall_avg = sum(
            r["avg_position"] * r["clicks"] for r in ranges if r["avg_position"] is not None
        ) / total_clicks if total_clicks > 0 else None

    # Ensure order from highest to lowest range for display
    range_order = ["1–3 (Топ-3)", "4–5", "6–10", "11–20", "21–50", ">50"]
    ranges.sort(key=lambda r: range_order.index(r["label"]) if r["label"] in range_order else 99)

    return {
        "project_id": project_id or "",
        "total_clicks": total_clicks,
        "ranges": ranges,
        "no_position_clicks": no_position_clicks,
        "overall_avg_position": round(overall_avg, 2) if overall_avg is not None else None,
    }
