"""Extract a structured business domain model from owner description.

Two-pass: LLM generates initial model → enricher validates regulatory facts
against authoritative sources → confidence classification applied.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

import anthropic

from ai_bos.config import settings
from ai_bos.logging_config import log

_client = anthropic.Anthropic(api_key=settings.anthropic_key)

DOMAIN_EXTRACTION_PROMPT = """You are a business operations analyst. Given a business description, extract a structured operational model.

Return ONLY valid JSON matching this schema:
{
  "business_type": "string",
  "industry_vertical": "string",
  "sub_vertical": "string or null",
  "geography": {"country": "string", "state": "string or null", "city": "string or null"},
  "customer_types": ["B2C" | "B2B" | "B2G"],
  "approximate_size": "solo | small | mid | enterprise",
  "stated_services": ["list of services"],
  "mandatory_operations": ["things this business MUST do to operate legally"],
  "probable_operations": ["things this type of business typically does"],
  "regulatory_domains": ["e.g. HIPAA", "state_dental_board", "PCI_DSS"],
  "required_integrations": ["e.g. insurance_clearinghouse", "payment_processor"],
  "ambiguities": ["things that are unclear and need owner clarification"],
  "verification_queue": ["specific facts that must be confirmed before acting on them"]
}

Be thorough about regulatory requirements — missing a compliance requirement is a serious failure."""


@dataclass
class BusinessDomain:
    business_type: str
    industry_vertical: str
    sub_vertical: str | None
    geography: dict
    customer_types: list[str]
    approximate_size: str
    stated_services: list[str]
    mandatory_operations: list[str]
    probable_operations: list[str]
    regulatory_domains: list[str]
    required_integrations: list[str]
    ambiguities: list[str]
    verification_queue: list[str]
    raw_extraction: dict = field(default_factory=dict)


def extract_domain(description: str) -> BusinessDomain:
    """Turn a plain-English business description into a structured domain model."""
    log.info("domain_extractor.start", description_length=len(description))

    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=DOMAIN_EXTRACTION_PROMPT,
        messages=[{"role": "user", "content": description}],
    )

    raw = json.loads(response.content[0].text)
    log.info(
        "domain_extractor.complete",
        business_type=raw.get("business_type"),
        regulatory_domains=raw.get("regulatory_domains"),
    )
    return BusinessDomain(
        business_type=raw["business_type"],
        industry_vertical=raw["industry_vertical"],
        sub_vertical=raw.get("sub_vertical"),
        geography=raw.get("geography", {}),
        customer_types=raw.get("customer_types", []),
        approximate_size=raw.get("approximate_size", "small"),
        stated_services=raw.get("stated_services", []),
        mandatory_operations=raw.get("mandatory_operations", []),
        probable_operations=raw.get("probable_operations", []),
        regulatory_domains=raw.get("regulatory_domains", []),
        required_integrations=raw.get("required_integrations", []),
        ambiguities=raw.get("ambiguities", []),
        verification_queue=raw.get("verification_queue", []),
        raw_extraction=raw,
    )
