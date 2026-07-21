"""Process inbound communications (email, SMS, voice webhooks)."""

from ai_bos.workers.celery_app import app
from ai_bos.logging_config import log


@app.task(bind=True, max_retries=3, default_retry_delay=60, name="ai_bos.workers.tasks.ingestion.process_inbound")
def process_inbound(self, business_id: str, channel: str, payload: dict) -> dict:  # type: ignore[no-untyped-def]
    """Route an inbound message to the appropriate agent."""
    try:
        log.info("process_inbound", business_id=business_id, channel=channel)
        # Orchestrator dispatch wired in Layer 4
        return {"status": "queued", "business_id": business_id}
    except Exception as exc:
        raise self.retry(exc=exc) from exc
