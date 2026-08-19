"""Dental vocabulary over the generic object graph.

Everything here is data. No dental concept appears in the domain engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class ServiceTemplate:
    name: str
    code: str
    code_system: str = "CDT"
    duration_minutes: int = 30
    default_price: Decimal | None = None
    required_resource_types: tuple[str, ...] = ("operatory", "dentist")


@dataclass(frozen=True)
class VerticalPack:
    vertical: str
    services: tuple[ServiceTemplate, ...]
    resource_types: tuple[str, ...]
    document_types: tuple[str, ...]
    regulated_document_types: frozenset[str]
    party_roles: dict[str, str] = field(default_factory=dict)

    def is_regulated(self, document_type: str) -> bool:
        return document_type in self.regulated_document_types


# Prices are deliberately absent for anything that varies by plan, materials or
# provider. A missing price forces a quote through the trust ramp instead of
# letting the system state a number it cannot stand behind.
DENTAL_SERVICES: tuple[ServiceTemplate, ...] = (
    ServiceTemplate("Periodic exam", "D0120", duration_minutes=20,
                    default_price=Decimal("65")),
    ServiceTemplate("Comprehensive exam", "D0150", duration_minutes=45,
                    default_price=Decimal("120")),
    ServiceTemplate("Bitewing x-rays", "D0272", duration_minutes=15,
                    default_price=Decimal("45")),
    ServiceTemplate("Adult prophylaxis", "D1110", duration_minutes=45,
                    default_price=Decimal("110")),
    ServiceTemplate("Child prophylaxis", "D1120", duration_minutes=30,
                    default_price=Decimal("85")),
    ServiceTemplate("Fluoride varnish", "D1206", duration_minutes=10,
                    default_price=Decimal("35")),
    # Restorative work varies by surface count and material — no listed price.
    ServiceTemplate("Amalgam restoration", "D2140", duration_minutes=45),
    ServiceTemplate("Composite restoration", "D2391", duration_minutes=60),
    ServiceTemplate("Crown, porcelain/ceramic", "D2740", duration_minutes=90),
    ServiceTemplate("Root canal, molar", "D3330", duration_minutes=120,
                    required_resource_types=("operatory", "endodontist")),
    ServiceTemplate("Extraction, erupted tooth", "D7140", duration_minutes=45),
    ServiceTemplate("Periodontal scaling, per quadrant", "D4341",
                    duration_minutes=60,
                    required_resource_types=("operatory", "hygienist")),
)

DENTAL_PACK = VerticalPack(
    vertical="dental",
    services=DENTAL_SERVICES,
    resource_types=("operatory", "dentist", "hygienist", "endodontist", "imaging"),
    document_types=(
        "clinical_note", "treatment_plan", "perio_chart", "odontogram",
        "radiograph", "consent_form", "referral", "insurance_card",
    ),
    # These carry PHI; the compliance gates key off this set rather than
    # guessing from content alone.
    regulated_document_types=frozenset(
        {
            "clinical_note", "treatment_plan", "perio_chart", "odontogram",
            "radiograph", "referral",
        }
    ),
    party_roles={
        "CUSTOMER": "patient",
        "STAFF": "provider",
        "PAYER": "insurer",
        "VENDOR": "lab",
    },
)


def service_by_code(code: str) -> ServiceTemplate | None:
    return next((s for s in DENTAL_SERVICES if s.code == code), None)
