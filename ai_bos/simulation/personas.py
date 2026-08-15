"""Customers with continuous identity across a simulation run.

Identity resolution is one of the first things that breaks in production, so
personas deliberately carry the messy properties real contacts have: multiple
phone numbers, shared household email, name variants, and contact details that
change partway through a run.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field


FIRST_NAMES = [
    "Maria", "James", "Aisha", "Robert", "Linh", "Sofia", "Daniel", "Grace",
    "Omar", "Rebecca", "Thomas", "Priya", "Michael", "Elena", "David", "Yuki",
]
LAST_NAMES = [
    "Alvarez", "Chen", "Okafor", "Nguyen", "Patel", "Rossi", "Novak", "Silva",
    "Kim", "Hassan", "Murphy", "Andersson", "Costa", "Haddad", "Weber", "Diaz",
]


@dataclass
class Persona:
    """A simulated customer. Identity is deliberately imperfect."""

    persona_id: uuid.UUID = field(default_factory=uuid.uuid4)
    given_name: str = ""
    family_name: str = ""

    # A persona may hold several of each over a run.
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)

    # Identity noise
    name_variants: list[str] = field(default_factory=list)
    shares_email_with: uuid.UUID | None = None
    changed_phone_mid_run: bool = False

    # Behaviour
    verbosity: str = "normal"      # terse | normal | rambling
    politeness: str = "neutral"    # warm | neutral | irritated
    is_existing_customer: bool = True

    history: list[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.given_name} {self.family_name}".strip()

    @property
    def primary_email(self) -> str:
        return self.emails[0] if self.emails else ""

    @property
    def primary_phone(self) -> str:
        return self.phones[0] if self.phones else ""

    def contact_used_at(self, rng: random.Random) -> tuple[str, str]:
        """Pick which email/phone this persona happens to use right now.

        Returns (email, phone) — either may be empty. A persona with several
        contact points does not consistently use the same one, which is exactly
        the case that defeats naive identity matching.
        """
        email = rng.choice(self.emails) if self.emails else ""
        phone = rng.choice(self.phones) if self.phones else ""
        return email, phone


class PersonaPool:
    """Builds and holds the cast for a simulation run.

    Roughly a fifth of the pool is given an identity defect, matching the
    observation that identity ambiguity is common rather than exotic.
    """

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)
        self._personas: list[Persona] = []

    def generate(self, count: int) -> list[Persona]:
        for i in range(count):
            p = self._make_persona(i)
            self._personas.append(p)
        self._inject_identity_defects()
        return self._personas

    def _make_persona(self, index: int) -> Persona:
        rng = self._rng
        given = rng.choice(FIRST_NAMES)
        family = rng.choice(LAST_NAMES)
        slug = f"{given.lower()}.{family.lower()}{index}"
        return Persona(
            given_name=given,
            family_name=family,
            emails=[f"{slug}@example.com"],
            phones=[f"+1555{rng.randint(1000000, 9999999)}"],
            verbosity=rng.choices(
                ["terse", "normal", "rambling"], weights=[0.3, 0.5, 0.2]
            )[0],
            politeness=rng.choices(
                ["warm", "neutral", "irritated"], weights=[0.25, 0.6, 0.15]
            )[0],
            is_existing_customer=rng.random() < 0.7,
        )

    def _inject_identity_defects(self) -> None:
        """Make ~20% of the pool hard to resolve."""
        rng = self._rng
        for p in self._personas:
            roll = rng.random()
            if roll < 0.07:
                # Second phone appears partway through the run.
                p.phones.append(f"+1555{rng.randint(1000000, 9999999)}")
                p.changed_phone_mid_run = True
            elif roll < 0.13:
                # Nickname / maiden name variant.
                p.name_variants.append(f"{p.given_name[:3]} {p.family_name}")
                p.name_variants.append(p.family_name)
            elif roll < 0.20 and len(self._personas) > 1:
                # Household sharing one email address.
                other = rng.choice([q for q in self._personas if q is not p])
                p.emails = list(other.emails)
                p.shares_email_with = other.persona_id

    @property
    def personas(self) -> list[Persona]:
        return self._personas
