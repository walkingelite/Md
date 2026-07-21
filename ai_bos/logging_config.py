"""Structured JSON logging with full audit context on every line."""

import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,  # False so reconfiguring in tests works
    )


def bind_audit_context(
    *,
    business_id: str | None = None,
    agent_id: str | None = None,
    task_id: str | None = None,
    action_id: str | None = None,
) -> None:
    """Bind identifiers so every log line in this context carries them."""
    ctx: dict[str, str] = {}
    if business_id:
        ctx["business_id"] = business_id
    if agent_id:
        ctx["agent_id"] = agent_id
    if task_id:
        ctx["task_id"] = task_id
    if action_id:
        ctx["action_id"] = action_id
    structlog.contextvars.bind_contextvars(**ctx)


def clear_audit_context() -> None:
    structlog.contextvars.clear_contextvars()


log = structlog.get_logger()
