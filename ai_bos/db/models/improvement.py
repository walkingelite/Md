"""Self-improvement models — outcomes and experiments."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Float, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_bos.db.base import Base, TimestampMixin, UUIDMixin


class Outcome(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "outcomes"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_profiles.id"), nullable=False, index=True
    )
    action_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("action_log.id"), nullable=True
    )
    intended_result: Mapped[str] = mapped_column(Text, nullable=False)
    measured_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    measurement_method: Mapped[str] = mapped_column(Text, nullable=False)
    success: Mapped[bool | None] = mapped_column(nullable=True)  # None until measured
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    contributing_factors: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    measured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Experiment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "experiments"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_profiles.id"), nullable=False, index=True
    )
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    variant_a_desc: Mapped[str] = mapped_column(Text, nullable=False)
    variant_b_desc: Mapped[str] = mapped_column(Text, nullable=False)
    traffic_split_pct: Mapped[float] = mapped_column(Float, nullable=False, default=20.0)
    # pending | running | concluded | rolled_back
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    concluded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
