"""Immutable action log — every real-world action ever taken."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_bos.db.base import Base, TimestampMixin, UUIDMixin


class ActionLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "action_log"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_profiles.id"), nullable=False, index=True
    )
    agent_type: Mapped[str] = mapped_column(Text, nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # PENDING | EXECUTED | CONFIRMED | FAILED | ROLLED_BACK
    status: Mapped[str] = mapped_column(Text, nullable=False, default="PENDING")

    # Idempotency: same key = return prior result
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    dry_run: Mapped[bool] = mapped_column(nullable=False, default=False)

    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
