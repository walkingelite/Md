"""Mapping a source system's rows onto domain events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from ai_bos.domain.events import DomainEvent, EventSource, EventType


@dataclass(frozen=True)
class ColumnMapping:
    """One source column mapped onto a payload field."""

    source_column: str
    target_field: str
    transform: Callable[[Any], Any] | None = None
    required: bool = False

    def extract(self, row: dict[str, Any]) -> Any:
        raw = row.get(self.source_column)
        if raw in (None, ""):
            return None
        return self.transform(raw) if self.transform else raw


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
    return None


def _split_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value).split(";") if part.strip()]


@dataclass
class SourceMapper:
    """Turns rows from one source table into events of one type."""

    name: str
    event_type: EventType
    columns: list[ColumnMapping]

    # Which source column holds the prior system's identifier. Retained so a
    # re-run matches the same entity instead of duplicating it, and so support
    # staff can still find a record by its old number.
    external_id_column: str = "id"
    occurred_at_column: str | None = None

    def map_row(
        self,
        row: dict[str, Any],
        business_id: uuid.UUID,
        id_resolver: Callable[[str, str], uuid.UUID],
    ) -> DomainEvent | None:
        external_id = str(row.get(self.external_id_column, "")).strip()
        if not external_id:
            return None

        payload: dict[str, Any] = {}
        for mapping in self.columns:
            value = mapping.extract(row)
            if value is None:
                if mapping.required:
                    return None
                continue
            payload[mapping.target_field] = value

        payload["external_id"] = external_id
        payload["external_source"] = self.name

        occurred = (
            _parse_datetime(row.get(self.occurred_at_column))
            if self.occurred_at_column
            else None
        )

        return DomainEvent(
            event_type=self.event_type,
            business_id=business_id,
            stream_id=id_resolver(self.name, external_id),
            payload=payload,
            source=EventSource.IMPORTED,
            # Falling back to now would date twenty-year-old history to today.
            occurred_at=occurred or datetime(1970, 1, 1, tzinfo=timezone.utc),
            actor="import",
        )


GENERIC_CSV_MAPPER: dict[str, SourceMapper] = {
    "parties": SourceMapper(
        name="parties",
        event_type=EventType.PARTY_REGISTERED,
        occurred_at_column="created_at",
        columns=[
            ColumnMapping("name", "display_name", required=True),
            ColumnMapping("email", "emails", _split_list),
            ColumnMapping("phone", "phones", _split_list),
        ],
    ),
    "bookings": SourceMapper(
        name="bookings",
        event_type=EventType.BOOKING_REQUESTED,
        occurred_at_column="start_time",
        columns=[
            ColumnMapping("start_time", "starts_at",
                          lambda v: (_parse_datetime(v) or "").isoformat()
                          if _parse_datetime(v) else None,
                          required=True),
            ColumnMapping("end_time", "ends_at",
                          lambda v: (_parse_datetime(v) or "").isoformat()
                          if _parse_datetime(v) else None),
            ColumnMapping("notes", "notes"),
        ],
    ),
    "obligations": SourceMapper(
        name="obligations",
        event_type=EventType.OBLIGATION_CREATED,
        occurred_at_column="created_at",
        columns=[
            ColumnMapping("amount", "amount", lambda v: str(v).replace("$", "").strip(),
                          required=True),
            ColumnMapping("type", "obligation_type"),
        ],
    ),
}
