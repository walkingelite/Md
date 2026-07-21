"""Background learning and pattern recognition jobs."""

from ai_bos.workers.celery_app import app
from ai_bos.logging_config import log


@app.task(name="ai_bos.workers.tasks.improvement.recognize_patterns")
def recognize_patterns() -> dict:  # type: ignore[no-untyped-def]
    """Weekly pattern recognition across all active businesses."""
    log.info("recognize_patterns_started")
    return {"status": "ok"}
