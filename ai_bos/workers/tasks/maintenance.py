"""Staleness refresh and cleanup tasks."""

from ai_bos.workers.celery_app import app
from ai_bos.logging_config import log


@app.task(name="ai_bos.workers.tasks.maintenance.check_staleness")
def check_staleness() -> dict:  # type: ignore[no-untyped-def]
    """Hourly: find stale facts and queue them for refresh."""
    log.info("staleness_check_started")
    return {"status": "ok"}
