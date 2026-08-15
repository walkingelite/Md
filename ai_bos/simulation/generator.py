"""Turns personas and scenarios into an inbound event stream.

Emits `BusinessEvent` — the exact type the orchestrator consumes in production.
There is deliberately no `simulated=True` field on the event: if business logic
could see it, the code path under test would not be the code path that ships.
Provenance is tracked out of band, in the harness transcript.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ai_bos.agents.orchestrator import BusinessEvent, EventType
from ai_bos.simulation.clock import SimClock
from ai_bos.simulation.personas import Persona, PersonaPool
from ai_bos.simulation.scenarios import SCENARIO_CATALOG, Difficulty, Scenario

CHANNEL_TO_EVENT_TYPE = {
    "EMAIL": EventType.INBOUND_EMAIL,
    "SMS": EventType.INBOUND_SMS,
    "VOICE": EventType.INBOUND_CALL,
}

# Difficulty mix. Weighted toward hard cases on purpose: the generator's job is
# to find failures, not to reproduce a typical day.
DEFAULT_DIFFICULTY_WEIGHTS = {
    Difficulty.BASELINE: 0.25,
    Difficulty.HARD: 0.50,
    Difficulty.BRUTAL: 0.25,
}


@dataclass
class GeneratedEvent:
    """A BusinessEvent plus the out-of-band provenance the harness needs."""

    event: BusinessEvent
    scenario: Scenario
    persona: Persona
    scheduled_at: datetime
    surface_text: str
    contact_email: str = ""
    contact_phone: str = ""


@dataclass
class EventGenerator:
    """Deterministic given a seed."""

    clock: SimClock
    business_id: uuid.UUID
    seed: int = 0
    personas: PersonaPool | None = None
    difficulty_weights: dict[Difficulty, float] = field(
        default_factory=lambda: dict(DEFAULT_DIFFICULTY_WEIGHTS)
    )
    _rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        if self.personas is None:
            self.personas = PersonaPool(seed=self.seed)
            self.personas.generate(24)

    def generate_days(self, days: int, events_per_day: int = 12) -> list[GeneratedEvent]:
        """Produce a chronologically ordered stream spanning `days`."""
        out: list[GeneratedEvent] = []
        cursor = self.clock.next_open(self.clock.start)

        for _ in range(days):
            day_start = cursor.replace(
                hour=self.clock.open_hour, minute=0, second=0, microsecond=0
            )
            count = max(1, int(self._rng.gauss(events_per_day, events_per_day * 0.3)))
            for _ in range(count):
                moment = self._arrival_within_day(day_start)
                generated = self._make_event(moment)
                if generated is not None:
                    out.append(generated)
            cursor = self.clock.next_open(day_start + timedelta(days=1))

        out.sort(key=lambda g: g.scheduled_at)
        return out

    def _arrival_within_day(self, day_start: datetime) -> datetime:
        """Arrivals cluster near opening and again after lunch.

        A uniform spread would understate the queue depth the system actually
        has to hold, which is where conflicting concurrent work shows up.
        """
        open_minutes = (self.clock.close_hour - self.clock.open_hour) * 60
        mode = self._rng.choice([60, 60, 90, 300, 330])
        offset = min(open_minutes - 1, max(0, int(self._rng.gauss(mode, 70))))
        return day_start + timedelta(minutes=offset)

    def _pick_scenario(self) -> Scenario:
        difficulties = list(self.difficulty_weights.keys())
        weights = [self.difficulty_weights[d] for d in difficulties]
        target = self._rng.choices(difficulties, weights=weights)[0]
        candidates = [s for s in SCENARIO_CATALOG if s.difficulty is target]
        return self._rng.choice(candidates or list(SCENARIO_CATALOG))

    def _make_event(self, moment: datetime) -> GeneratedEvent | None:
        assert self.personas is not None
        scenario = self._pick_scenario()

        pool = self.personas.personas
        if scenario.requires_prior_context:
            pool = [p for p in pool if p.is_existing_customer] or pool
        persona = self._rng.choice(pool)

        template = self._rng.choice(scenario.templates)
        text = template.format(name=persona.given_name)
        text = self._apply_voice(text, persona)

        email, phone = persona.contact_used_at(self._rng)
        event_type = CHANNEL_TO_EVENT_TYPE[scenario.channel]

        payload = {
            "channel": scenario.channel,
            "text": text,
            "from_email": email if scenario.channel == "EMAIL" else "",
            "from_phone": phone if scenario.channel in ("SMS", "VOICE") else "",
            "received_at": moment.isoformat(),
        }

        event = BusinessEvent(
            event_id=uuid.uuid4(),
            business_id=self.business_id,
            event_type=event_type,
            payload=payload,
            priority=3 if scenario.difficulty is Difficulty.BRUTAL else 5,
        )
        persona.history.append(scenario.scenario_id)

        return GeneratedEvent(
            event=event,
            scenario=scenario,
            persona=persona,
            scheduled_at=moment,
            surface_text=text,
            contact_email=email,
            contact_phone=phone,
        )

    def _apply_voice(self, text: str, persona: Persona) -> str:
        """Surface noise. Real inbound is not clean prose."""
        if persona.verbosity == "terse" and len(text) > 60:
            text = text.split(".")[0].strip()
        elif persona.verbosity == "rambling":
            text = f"{text} Sorry for the long message, thanks so much."

        if persona.politeness == "irritated":
            text = text.upper() if self._rng.random() < 0.2 else f"{text}!!"
        elif persona.politeness == "warm":
            text = f"Hi! {text} Thank you!"
        return text
