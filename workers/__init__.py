"""Celery worker configuration."""

from celery import Celery

app = Celery(
    "topinjector_workers",
    broker="redis://localhost:6379/10",
    backend="redis://localhost:6379/11",
)
app.config_from_object({
    "broker_url": "redis://localhost:6379/10",
    "result_backend": "redis://localhost:6379/11",
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
