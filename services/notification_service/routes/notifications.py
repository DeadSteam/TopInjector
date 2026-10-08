"""Notification routes. Base URL prefix handled by main.py."""

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["notifications"])


@router.get("/")
async def list_notifications(user_id: str = "", limit: int = 50, offset: int = 0):
    """Return paginated notifications for a user."""
    return {
        "notifications": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
    }


@router.post("/{notif_id}/read")
async def mark_notification_read(notif_id: str):
    """Mark a notification as read."""
    return {"id": notif_id, "read": True}
