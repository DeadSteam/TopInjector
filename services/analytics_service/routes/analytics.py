"""Analytics routes. Base URL prefix handled by main.py."""

from fastapi import APIRouter, Query

router = APIRouter(tags=["analytics"])


@router.get("/summary")
async def get_summary(project_id: str = Query(default=""), start_date: str = Query(default=""), end_date: str = Query(default="")):
    """Return aggregate stats: total clicks, avg position, geo distribution."""
    return {
        "project_id": project_id or "",
        "total_clicks": 0,
        "avg_position": None,
        "geo_distribution": {},
        "date_range": {"start": start_date or "", "end": end_date or ""},
    }


@router.get("/positions")
async def get_positions(project_id: str = Query(default=""), query_text: str = Query(default="")):
    """Return position history for queries."""
    return {
        "project_id": project_id or "",
        "query_text": query_text or "",
        "history": [],
    }


@router.get("/clicks")
async def get_clicks(project_id: str = Query(default=""), start_date: str = Query(default=""), end_date: str = Query(default="")):
    """Return click timeline data for charts."""
    return {
        "project_id": project_id or "",
        "timeline": [],
    }
