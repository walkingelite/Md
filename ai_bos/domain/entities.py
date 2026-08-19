"""The generic business object graph.

A dental practice, a plumbing company and a salon differ in vocabulary, not in
structure. Each has people it deals with, things it can book, things it sells,
things owed, and money moving. Naming these generically is what lets one system
of record serve any of them; vertical packs supply the words.

These are read models — projections rebuilt from the event log, never written
to directly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class PartyRole(str, Enum):
    CUSTOMER = "CUSTOMER"      # patient, client, guest
    STAFF = "STAFF"            # provider, technician, stylist
    VENDOR = "VENDOR"          # lab, supplier
    PAYER = "PAYER"            # insurer, warranty provider, financing
    OTHER = "OTHER"


@dataclass
class Party:
    """Anyone the business deals with. Replaces the narrower Customer."""

    party_id: uuid.UUID = field(default_factory=uuid.uuid4)
    roles: set[PartyRole] = field(default_factory=set)
    display_name: str = ""

    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    addresses: list[dict[str, str]] = field(default_factory=list)

    # Identity confidence travels with the record, because a party assembled
    # from an ambiguous match must not be treated like a verified one.
    identity_confidence: str = "LOW"
    merged_into: uuid.UUID | None = None

    consent: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)  # vertical-specific

    created_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.merged_into is None

    def has_role(self, role: PartyRole) -> bool:
        return role in self.roles


@dataclass
class Resource:
    """Anything with finite availability that a booking consumes.

    A chair, a room, a van, a practitioner's time. Modelling staff time as a
    resource rather than a special case is what makes double-booking a single
    check instead of several.
    """

    resource_id: uuid.UUID = field(default_factory=uuid.uuid4)
    name: str = ""
    resource_type: str = "generic"          # chair | room | vehicle | person
    party_id: uuid.UUID | None = None       # set when the resource is a person
    capacity: int = 1
    attributes: dict[str, Any] = field(default_factory=dict)
    active: bool = True


@dataclass
class Service:
    """Something the business sells."""

    service_id: uuid.UUID = field(default_factory=uuid.uuid4)
    name: str = ""
    code: str = ""                          # CDT, SKU, whatever the vertical uses
    code_system: str = ""                    # which coding scheme `code` belongs to
    duration_minutes: int = 30
    default_price: Decimal | None = None     # None means "quote required"
    required_resource_types: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    retired: bool = False

    @property
    def requires_quote(self) -> bool:
        """No listed price means a human decides. The trust ramp pins
        quote_price to DRAFT for exactly this reason."""
        return self.default_price is None


class BookingState(str, Enum):
    REQUESTED = "REQUESTED"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


@dataclass
class Booking:
    """A reservation of resources for a party at a time."""

    booking_id: uuid.UUID = field(default_factory=uuid.uuid4)
    party_id: uuid.UUID | None = None
    service_ids: list[uuid.UUID] = field(default_factory=list)
    resource_ids: list[uuid.UUID] = field(default_factory=list)

    starts_at: datetime | None = None
    ends_at: datetime | None = None
    state: BookingState = BookingState.REQUESTED

    notes: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.state in (BookingState.REQUESTED, BookingState.CONFIRMED)

    def overlaps(self, other: "Booking") -> bool:
        if not (self.starts_at and self.ends_at and other.starts_at and other.ends_at):
            return False
        return self.starts_at < other.ends_at and other.starts_at < self.ends_at

    def conflicts_with(self, other: "Booking") -> bool:
        """Two active bookings sharing a resource at overlapping times."""
        if not (self.is_active and other.is_active):
            return False
        if not set(self.resource_ids) & set(other.resource_ids):
            return False
        return self.overlaps(other)


class ObligationState(str, Enum):
    OPEN = "OPEN"
    SUBMITTED = "SUBMITTED"       # sent to a payer, awaiting adjudication
    SETTLED = "SETTLED"
    REJECTED = "REJECTED"
    WRITTEN_OFF = "WRITTEN_OFF"


@dataclass
class Obligation:
    """Something owed, in either direction.

    An invoice to a customer, a claim to an insurer, a warranty commitment back
    to a customer. One shape covers all of them because they share a lifecycle:
    created, possibly submitted, then settled, rejected or forgiven.
    """

    obligation_id: uuid.UUID = field(default_factory=uuid.uuid4)
    obligation_type: str = "invoice"          # invoice | claim | credit | commitment
    owed_by: uuid.UUID | None = None
    owed_to: uuid.UUID | None = None
    amount: Decimal = Decimal("0")
    currency: str = "USD"

    booking_id: uuid.UUID | None = None
    state: ObligationState = ObligationState.OPEN
    due_at: datetime | None = None

    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def is_outstanding(self) -> bool:
        return self.state in (ObligationState.OPEN, ObligationState.SUBMITTED)


@dataclass
class Transaction:
    """Money that actually moved. Distinct from an obligation, which is money
    that is merely supposed to move."""

    transaction_id: uuid.UUID = field(default_factory=uuid.uuid4)
    obligation_id: uuid.UUID | None = None
    party_id: uuid.UUID | None = None
    amount: Decimal = Decimal("0")
    currency: str = "USD"
    direction: str = "INBOUND"                # INBOUND | OUTBOUND
    method: str = ""                          # card | cash | ach | insurance
    occurred_at: datetime | None = None
    external_reference: str = ""
    refunded_amount: Decimal = Decimal("0")

    @property
    def net_amount(self) -> Decimal:
        return self.amount - self.refunded_amount


@dataclass
class Document:
    """Anything recorded about a party or booking.

    Amendment appends rather than overwrites; regulated records generally
    require the prior version to remain recoverable.
    """

    document_id: uuid.UUID = field(default_factory=uuid.uuid4)
    party_id: uuid.UUID | None = None
    booking_id: uuid.UUID | None = None
    document_type: str = "note"
    content: str = ""
    is_regulated: bool = False
    versions: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime | None = None

    @property
    def version_count(self) -> int:
        return len(self.versions) + 1
