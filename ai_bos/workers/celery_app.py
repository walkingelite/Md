"""Celery application — all tasks are idempotent by design."""

from celery import Celery

from ai_bos.config import settings

app = Celery(
    "ai_bos",
    broker=str(settings.redis_url),
    backend=str(settings.redis_url),
    include=[
        "ai_bos.workers.tasks.ingestion",
        "ai_bos.workers.tasks.scheduled",
        "ai_bos.workers.tasks.improvement",
        "ai_bos.workers.tasks.maintenance",
    ],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_always_eager=False,
    task_acks_late=True,       # Task only acked after successful completion
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=86400,      # 24 hours
    beat_schedule={
        "staleness-check": {
            "task": "ai_bos.workers.tasks.maintenance.check_staleness",
            "schedule": 3600.0,  # hourly
        },
        "pattern-recognition": {
            "task": "ai_bos.workers.tasks.improvement.recognize_patterns",
            "schedule": 604800.0,  # weekly
        },
    },
)
