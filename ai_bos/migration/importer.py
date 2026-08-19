"""Runs an import and reports honestly on what did and did not come across."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable

from ai_bos.domain.events import DomainEvent, EventSource
from ai_bos.domain.store import EventStore
from ai_bos.logging_config import log
from ai_bos.migration.mappers import SourceMapper


@dataclass
class ImportReport:
    rows_seen: int = 0
    events_created: int = 0
    rows_skipped: int = 0
    skip_reasons: dict[str, int] = field(default_factory=dict)
    per_source: dict[str, int] = field(default_factory=dict)
    external_id_map: dict[str, uuid.UUID] = field(default_factory=dict)

    def skip(self, reason: str) -> None:
        self.rows_skipped += 1
        self.skip_reasons[reason] = self.skip_reasons.get(reason, 0) + 1

    @property
    def success_rate(self) -> float:
        return self.events_created / self.rows_seen if self.rows_seen else 0.0

    def summary(self) -> str:
        lines = [
            "Import report",
            "=" * 44,
            f"rows seen       {self.rows_seen}",
            f"events created  {self.events_created}",
            f"rows skipped    {self.rows_skipped}",
            f"success rate    {self.success_rate:.1%}",
        ]
        if self.per_source:
            lines += ["", "By source:"]
            lines += [f"  {name:<24}{n:>6}" for name, n in sorted(self.per_source.items())]
        if self.skip_reasons:
            lines += ["", "Skipped because:"]
            lines += [
                f"  {reason:<24}{n:>6}"
                for reason, n in sorted(self.skip_reasons.items(), key=lambda kv: -kv[1])
            ]
        # Anything below total success needs a human decision about the
        # remainder, so it is stated rather than rounded away.
        if self.rows_skipped:
            lines += [
                "",
                f"! {self.rows_skipped} rows did not import. Review before cutover —",
                "  a silent partial migration is worse than a failed one.",
            ]
        return "\n".join(lines)


class Importer:
    """Maps a prior system's rows into the event log.

    Idempotent by external id: importing the same export twice produces the
    same entities rather than duplicating them, which matters because real
    migrations are run several times before cutover.
    """

    def __init__(
        self,
        business_id: uuid.UUID,
        store: EventStore,
        mappers: dict[str, SourceMapper],
    ) -> None:
        self.business_id = business_id
        self.store = store
        self.mappers = mappers
        self._id_map: dict[str, uuid.UUID] = {}

    def _resolve_id(self, source_name: str, external_id: str) -> uuid.UUID:
        key = f"{source_name}:{external_id}"
        if key not in self._id_map:
            # Deterministic, so a re-run maps the same source row to the same
            # entity even in a fresh process.
            self._id_map[key] = uuid.uuid5(
                uuid.NAMESPACE_URL, f"{self.business_id}/{key}"
            )
        return self._id_map[key]

    async def import_source(
        self, source_name: str, rows: Iterable[dict[str, Any]], report: ImportReport
    ) -> None:
        mapper = self.mappers.get(source_name)
        if mapper is None:
            log.warning("importer.unknown_source", source=source_name)
            return

        for row in rows:
            report.rows_seen += 1
            try:
                event = mapper.map_row(row, self.business_id, self._resolve_id)
            except Exception as exc:
                report.skip(f"mapping error: {type(exc).__name__}")
                continue

            if event is None:
                report.skip("missing required field")
                continue

            existing = await self.store.read_stream(event.stream_id)
            if any(e.event_type is event.event_type for e in existing):
                report.skip("already imported")
                continue

            await self.store.append([event])
            report.events_created += 1
            report.per_source[source_name] = report.per_source.get(source_name, 0) + 1
            report.external_id_map[
                f"{source_name}:{event.payload.get('external_id')}"
            ] = event.stream_id

    async def run(self, sources: dict[str, Iterable[dict[str, Any]]]) -> ImportReport:
        report = ImportReport()
        # Parties first: bookings and obligations reference them.
        ordered = sorted(sources.items(), key=lambda kv: kv[0] != "parties")
        for source_name, rows in ordered:
            await self.import_source(source_name, rows, report)

        log.info(
            "importer.complete",
            business_id=str(self.business_id),
            events=report.events_created,
            skipped=report.rows_skipped,
        )
        return report

    async def verify(self) -> dict[str, int]:
        """Count what actually landed, by source.

        Read back rather than trusting the write path: an import that reports
        success but leaves nothing queryable is the failure mode that destroys
        trust at cutover.
        """
        events = await self.store.read_all(self.business_id)
        imported = [e for e in events if e.source is EventSource.IMPORTED]
        counts: dict[str, int] = {}
        for event in imported:
            name = str(event.payload.get("external_source", "unknown"))
            counts[name] = counts.get(name, 0) + 1
        return counts
