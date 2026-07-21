"""Business profile and domain models."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_bos.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class BusinessProfile(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "business_profiles"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description_raw: Mapped[str] = mapped_column(Text, nullable=False)
    domain_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="onboarding"
    )  # onboarding | active | paused

    facts: Mapped[list["FactRecord"]] = relationship(back_populates="business")
    customers: Mapped[list["Customer"]] = relationship(back_populates="business")  # type: ignore[name-defined]


class FactRecord(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """Every piece of knowledge the system has, with full provenance.
    Hard-coded confidence gating: ASSUMED facts may not be acted on."""

    __tablename__ = "fact_records"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_profiles.id"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(Text, nullable=False)  # regulatory, customer, operational…
    key: Mapped[str] = mapped_column(Text, nullable=False)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Confidence and provenance
    confidence: Mapped[str] = mapped_column(Text, nullable=False)
    # OWNER_STATED | DOMAIN_CERTAIN | DOMAIN_TYPICAL | INFERRED | ASSUMED | UNKNOWN
    basis: Mapped[str] = mapped_column(Text, nullable=False)
    # OBSERVED | INFERRED | EXTERNAL | ASSUMED
    source_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    valid_from: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_until: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_verified_at: Mapped[str | None] = mapped_column(Text, nullable=True)

    business: Mapped["BusinessProfile"] = relationship(back_populates="facts")
