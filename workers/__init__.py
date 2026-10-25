"""Celery worker configuration."""

from celery import Celery

from shared.config import settings

_redis = f"redis://{settings.redis_auth}{settings.redis_host}:{settings.redis_port}"

app = Celery(
    "topinjector_workers",
    broker=f"{_redis}/10",
    backend=f"{_redis}/11",
)
app.config_from_object({
    "broker_url": f"{_redis}/10",
    "result_backend": f"{_redis}/11",
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "timezone": "UTC",
    "enable_utc": True,
    "beat_schedule": {
        "schedule-tasks-every-minute": {
            "task": "workers.scheduler.schedule_daily_tasks",
            "schedule": 60.0,
        },
        "check-stale-tasks-every-10-minutes": {
            "task": "workers.stale_checker.check_stale",
            "schedule": 600.0,
        },
    },
})

# Import task modules so Celery registers them
import workers.scheduler  # noqa: F401, E402
import workers.stale_checker  # noqa: F401, E402
