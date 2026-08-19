"""Pooling what instances learn, without pooling what they hold.

The distinction that makes this safe: a *pattern* is that businesses of a kind
get asked about payment plans. A *record* is that a named person asked. The
first travels to the fleet; the second never leaves the instance.

Submissions are stripped rather than trusted — an instance cannot opt into
sending records by mislabelling them, because the redaction happens here on
the way out.
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ai_bos.logging_config import log
from ai_bos.platform.tiers import ChangeKind

# Minimum distinct businesses that must independently observe a pattern before
# the fleet acts on it. One business's quirk is not a fleet-wide truth.
CORROBORATION_THRESHOLD = 3

_IDENTIFIER_PATTERNS = (
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),               # email
    re.compile(r"\+?\d[\d\s().-]{7,}\d"),                  # phone
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                  # national id
    re.compile(r"\b\d{1,5}\s+[A-Z][a-z]+\s+(St|Ave|Rd|Blvd|Lane|Dr)\b"),  # address
)

REDACTED = "[redacted]"


def redact(text: str) -> str:
    for pattern in _IDENTIFIER_PATTERNS:
        text = pattern.sub(REDACTED, text)
    return text


@dataclass
class PatternSubmission:
    """One instance reporting something it learned."""

    kind: ChangeKind
    business_id: uuid.UUID
    vertical: str
    signature: str                 # what the pattern is, in normalised form
    description: str = ""
    example_text: str = ""
    submitted_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def redacted(self) -> "PatternSubmission":
        from dataclasses import replace

        return replace(
            self,
            description=redact(self.description),
            example_text=redact(self.example_text),
        )


@dataclass
class FleetPattern:
    signature: str
    vertical: str
    kind: ChangeKind
    observing_businesses: set[uuid.UUID] = field(default_factory=set)
    descriptions: list[str] = field(default_factory=list)

    @property
    def corroboration(self) -> int:
        return len(self.observing_businesses)

    @property
    def is_corroborated(self) -> bool:
        return self.corroboration >= CORROBORATION_THRESHOLD


class FleetLearning:
    """The creator's view across every instance."""

    def __init__(self) -> None:
        self._patterns: dict[str, FleetPattern] = {}
        self._rejected: list[tuple[str, str]] = []

    def submit(self, submission: PatternSubmission) -> FleetPattern | None:
        clean = submission.redacted()

        if clean.description != submission.description or clean.example_text != submission.example_text:
            log.info(
                "federation.redacted_on_ingest",
                business_id=str(submission.business_id),
                signature=submission.signature,
            )

        if not clean.signature.strip():
            self._rejected.append((str(submission.business_id), "empty signature"))
            return None

        key = f"{clean.vertical}:{clean.signature}"
        pattern = self._patterns.get(key)
        if pattern is None:
            pattern = FleetPattern(
                signature=clean.signature, vertical=clean.vertical, kind=clean.kind
            )
            self._patterns[key] = pattern

        pattern.observing_businesses.add(clean.business_id)
        if clean.description and clean.description not in pattern.descriptions:
            if len(pattern.descriptions) < 5:
                pattern.descriptions.append(clean.description)
        return pattern

    def corroborated(self, vertical: str | None = None) -> list[FleetPattern]:
        """Patterns seen independently by enough businesses to act on."""
        patterns = [p for p in self._patterns.values() if p.is_corroborated]
        if vertical:
            patterns = [p for p in patterns if p.vertical == vertical]
        return sorted(patterns, key=lambda p: -p.corroboration)

    def emerging(self, vertical: str | None = None) -> list[FleetPattern]:
        patterns = [p for p in self._patterns.values() if not p.is_corroborated]
        if vertical:
            patterns = [p for p in patterns if p.vertical == vertical]
        return sorted(patterns, key=lambda p: -p.corroboration)

    def summary(self) -> str:
        corroborated = self.corroborated()
        lines = [
            "Fleet learning",
            "=" * 44,
            f"distinct patterns   {len(self._patterns)}",
            f"corroborated        {len(corroborated)}"
            f" (>= {CORROBORATION_THRESHOLD} businesses)",
        ]
        if corroborated:
            lines += ["", "Ready to ship as a pack update:"]
            lines += [
                f"  {p.signature:<40}{p.corroboration:>4} businesses"
                for p in corroborated[:10]
            ]
        return "\n".join(lines)
