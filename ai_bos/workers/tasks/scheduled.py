"""Time-triggered business operations."""

from ai_bos.workers.celery_app import app
from ai_bos.logging_config import log


@app.task(bind=True, name="ai_bos.workers.tasks.scheduled.run_scheduled_operation")
def run_scheduled_operation(self, business_id: str, operation_type: str, params: dict) -> dict:  # type: ignore[no-untyped-def]
    log.info("run_scheduled_operation", business_id=business_id, operation_type=operation_type)
    return {"status": "ok"}
