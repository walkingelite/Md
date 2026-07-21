"""Web enricher — validates regulatory and domain facts against authoritative sources.

Every fact it produces includes a source URL stored as a citation.
No source = fact cannot exceed INFERRED confidence.
"""

from __future__ import annotations

import httpx
from dataclasses import dataclass

from ai_bos.logging_config import log


@dataclass
class EnrichedFact:
    domain: str
    key: str
    value: dict
    source_url: str
    source_text_excerpt: str


class BusinessEnricher:
    """Fetches authoritative regulatory information for a business domain."""

    async def enrich_regulatory(
        self, regulatory_domains: list[str], geography: dict
    ) -> list[EnrichedFact]:
        """
        For each regulatory domain, find the authoritative source and
        extract the relevant requirements.

        Currently wired to fetch from known government URL patterns.
        In production: integrate with a search API to find sources dynamically.
        """
        facts: list[EnrichedFact] = []

        for reg_domain in regulatory_domains:
            source_url = self._known_source(reg_domain, geography)
            if not source_url:
                log.warning("enricher.no_source", regulatory_domain=reg_domain)
                continue

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(source_url, follow_redirects=True)
                    if resp.status_code == 200:
                        excerpt = resp.text[:2000]  # Store first 2000 chars as citation
                        facts.append(
                            EnrichedFact(
                                domain="regulatory_requirement",
                                key=reg_domain,
                                value={"name": reg_domain, "source_url": source_url},
                                source_url=source_url,
                                source_text_excerpt=excerpt,
                            )
                        )
                        log.info("enricher.fact_found", reg_domain=reg_domain, source_url=source_url)
            except Exception as exc:
                log.warning("enricher.fetch_failed", reg_domain=reg_domain, error=str(exc))

        return facts

    def _known_source(self, reg_domain: str, geography: dict) -> str | None:
        """Map a regulatory domain name to its authoritative source URL."""
        state = geography.get("state", "").upper()
        country = geography.get("country", "US")

        known: dict[str, str] = {
            "HIPAA": "https://www.hhs.gov/hipaa/for-professionals/security/index.html",
            "PCI_DSS": "https://www.pcisecuritystandards.org/document_library/",
            "GDPR": "https://gdpr-info.eu/",
            "CAN_SPAM": "https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business",
            "TCPA": "https://www.fcc.gov/consumers/guides/stopping-unwanted-calls-and-texts",
        }
        return known.get(reg_domain)
