"""Celery worker configuration."""

import os

from celery import Celery

_redis_host = os.getenv("REDIS_HOST", "localhost")

app = Celery(
    "topinjector_workers",
    broker=f"redis://{_redis_host}:6379/10",
    backend=f"redis://{_redis_host}:6379/11",
)
app.config_from_object({
    "broker_url": f"redis://{_redis_host}:6379/10",
    "result_backend": f"redis://{_redis_host}:6379/11",
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
