"""How many strategy tasks a project should get, per the rules of its schedule type.

- daily:   the day's quota is ``daily_limit``, released evenly across the scheduling window
- hourly:  the same quota, released in equal batches at the start of each window hour
- monthly: ``daily_limit`` is the month's quota; each day gets its share, released like daily

The window is ``scheduling_window`` = {"start": "HH:MM", "end": "HH:MM"} (whole day if unset).
All times are local to SCHEDULE_TIMEZONE.
"""

import calendar
import math
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from services.project_service.domain.models import Project
from shared.config import settings


def local_now(now: datetime | None = None) -> datetime:
    """``now`` (default: current time) in the scheduling timezone."""
    return (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(settings.schedule_timezone))


def local_day_start(now: datetime | None = None) -> datetime:
    """Start of today in the scheduling timezone, as a UTC datetime (for DB comparisons)."""
    return local_now(now).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def _parse_hhmm(value: object) -> time | None:
    try:
        hours, minutes = str(value).split(":")
        return time(int(hours), int(minutes))
    except (TypeError, ValueError):
        return None


def window(project: Project, day: datetime) -> tuple[datetime, datetime]:
    """Start and end of the project's working window on ``day`` (local, tz-aware)."""
    midnight = day.replace(hour=0, minute=0, second=0, microsecond=0)
    cfg = project.scheduling_window or {}
    start, end = _parse_hhmm(cfg.get("start")), _parse_hhmm(cfg.get("end"))
    if start is None or end is None or end <= start:
        return midnight, midnight + timedelta(days=1)
    return datetime.combine(midnight.date(), start, day.tzinfo), datetime.combine(midnight.date(), end, day.tzinfo)


def quota_for_day(project: Project, now_local: datetime) -> int:
    """The project's whole strategy quota for the local day of ``now_local``."""
    limit = max(project.daily_limit or 0, 0)
    if project.strategy_type == "monthly":
        days = calendar.monthrange(now_local.year, now_local.month)[1]
        day = now_local.day
        return limit * day // days - limit * (day - 1) // days  # today's share of the monthly quota
    return limit


def due_by(project: Project, now_local: datetime) -> int:
    """How many strategy tasks the project should have received today by ``now_local``."""
    start, end = window(project, now_local)
    if now_local < start:
        return 0
    quota = quota_for_day(project, now_local)

    if project.strategy_type == "hourly":
        hours_total = math.ceil((end - start) / timedelta(hours=1))
        hours_started = min(int((now_local - start) / timedelta(hours=1)) + 1, hours_total)
        return math.ceil(quota * hours_started / hours_total)

    elapsed = min((now_local - start) / (end - start), 1.0)
    return math.floor(quota * elapsed + 1e-9)
