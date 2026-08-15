"""Generator: determinism, protocol identity, and stream shape."""

import uuid
from datetime import datetime, timezone

from ai_bos.agents.orchestrator import BusinessEvent, EventType
from ai_bos.simulation.clock import SimClock
from ai_bos.simulation.generator import EventGenerator


def _gen(seed: int = 11) -> EventGenerator:
    clock = SimClock(start=datetime(2026, 1, 7, 8, 0, tzinfo=timezone.utc))
    return EventGenerator(clock=clock, business_id=uuid.uuid4(), seed=seed)


def test_stream_is_deterministic_for_a_seed():
    a = [g.surface_text for g in _gen(11).generate_days(5)]
    b = [g.surface_text for g in _gen(11).generate_days(5)]
    assert a == b


def test_different_seeds_produce_different_streams():
    a = [g.surface_text for g in _gen(1).generate_days(5)]
    b = [g.surface_text for g in _gen(2).generate_days(5)]
    assert a != b


def test_emits_real_business_events():
    """Protocol identity: the orchestrator must not be able to tell these
    apart from production traffic."""
    for g in _gen().generate_days(3):
        assert isinstance(g.event, BusinessEvent)
        assert isinstance(g.event.event_type, EventType)
        assert g.event.business_id
        assert "text" in g.event.payload


def test_event_payload_carries_no_simulation_marker():
    """If business logic can detect simulation, the tested path is not the
    shipped path."""
    for g in _gen().generate_days(3):
        keys = {k.lower() for k in g.event.payload}
        assert not any("sim" in k or "fake" in k or "test" in k for k in keys)


def test_stream_is_chronologically_ordered():
    stream = _gen().generate_days(6)
    times = [g.scheduled_at for g in stream]
    assert times == sorted(times)


def test_events_land_within_business_hours():
    gen = _gen()
    for g in gen.generate_days(5):
        assert gen.clock.open_hour <= g.scheduled_at.hour < gen.clock.close_hour
        assert g.scheduled_at.weekday() in gen.clock.workdays


def test_volume_scales_with_days():
    short = _gen().generate_days(2)
    long = _gen().generate_days(10)
    assert len(long) > len(short) * 2


def test_prior_context_scenarios_use_existing_customers():
    for g in _gen().generate_days(10):
        if g.scenario.requires_prior_context:
            assert g.persona.is_existing_customer


def test_contact_details_match_channel():
    for g in _gen().generate_days(5):
        if g.scenario.channel == "EMAIL":
            assert g.event.payload["from_email"]
        else:
            assert g.event.payload["from_phone"]
