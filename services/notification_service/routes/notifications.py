"""Notification routes. Base URL prefix handled by main.py."""

from fastapi import APIRouter, Depends

from shared.auth.access import request_user_id

# Every notification route requires an authenticated caller.
router = APIRouter(tags=["notifications"], dependencies=[Depends(request_user_id)])


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


@router.post("/mark-all-read")
async def mark_all_notifications_read():
    """Mark all notifications for the current user as read."""
    return {"marked": True}
