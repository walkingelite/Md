"""Personas: determinism and deliberate identity defects."""

from ai_bos.simulation.personas import PersonaPool


def test_pool_is_deterministic_for_a_seed():
    a = PersonaPool(seed=42).generate(20)
    b = PersonaPool(seed=42).generate(20)
    assert [p.full_name for p in a] == [p.full_name for p in b]
    assert [p.emails for p in a] == [p.emails for p in b]


def test_different_seeds_differ():
    a = PersonaPool(seed=1).generate(20)
    b = PersonaPool(seed=2).generate(20)
    assert [p.full_name for p in a] != [p.full_name for p in b]


def test_every_persona_has_contact_details():
    for p in PersonaPool(seed=7).generate(30):
        assert p.emails and p.phones
        assert p.full_name.strip()


def test_pool_contains_identity_defects():
    """~20% of personas should be hard to resolve. Without these the run is
    a fair-weather test and identity handling is never exercised."""
    pool = PersonaPool(seed=3).generate(60)
    defective = [
        p for p in pool
        if p.changed_phone_mid_run or p.name_variants or p.shares_email_with
    ]
    assert len(defective) >= 5, "identity defects missing from pool"


def test_contact_used_at_is_drawn_from_persona():
    import random
    pool = PersonaPool(seed=5).generate(10)
    rng = random.Random(0)
    for p in pool:
        email, phone = p.contact_used_at(rng)
        assert email in p.emails
        assert phone in p.phones
