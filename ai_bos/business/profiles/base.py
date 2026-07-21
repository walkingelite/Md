"""Base domain profile template."""

from dataclasses import dataclass, field


@dataclass
class DomainProfile:
    """Starting-point knowledge for a business type.
    Owner-stated facts always override these."""
    mandatory_operations: list[str] = field(default_factory=list)
    regulatory_domains: list[str] = field(default_factory=list)
    typical_integrations: list[str] = field(default_factory=list)
    customer_lifecycle: list[str] = field(default_factory=list)
    verification_items: list[str] = field(default_factory=list)
