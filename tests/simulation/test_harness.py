"""Harness: failure detection, gap collection, coverage reporting."""

import uuid
from datetime import datetime, timezone

from ai_bos.simulation.harness import SimulationHarness


def _harness(seed: int = 5) -> SimulationHarness:
    return SimulationHarness(
        business_id=uuid.uuid4(),
        start=datetime(2026, 1, 7, 8, 0, tzinfo=timezone.utc),
        seed=seed,
    )


async def _null_handler(generated) -> dict:
    """Handles nothing. Every assertion should fail."""
    return {"assertions_held": []}


async def _perfect_handler(generated) -> dict:
    """Satisfies whatever the scenario demands."""
    return {"assertions_held": list(generated.scenario.must_hold)}


async def _gap_handler(generated) -> dict:
    return {
        "assertions_held": list(generated.scenario.must_hold),
        "gap": f"unknown:{generated.scenario.category.value}",
    }


async def _exploding_handler(generated) -> dict:
    raise RuntimeError("handler blew up")


async def test_null_handler_fails_everything():
    report = await _harness().run(_null_handler, days=5)
    assert report.events_total > 0
    assert report.failure_count > 0
    assert report.events_handled == report.events_total


async def test_perfect_handler_finds_no_failures():
    report = await _harness().run(_perfect_handler, days=5)
    assert report.failure_count == 0
    assert report.events_handled == report.events_total


async def test_handler_errors_are_counted_not_raised():
    report = await _harness().run(_exploding_handler, days=3)
    assert report.handler_errors == report.events_total
    assert report.events_handled == 0


async def test_gaps_are_collected_and_deduplicated():
    report = await _harness().run(_gap_handler, days=6)
    assert report.gaps
    for entry in report.gaps.values():
        assert entry.times_seen >= 1
        assert len(entry.example_texts) <= 3


async def test_ranked_gaps_do_not_rank_by_count():
    """Simulated frequency reflects generator config, not real demand."""
    report = await _harness().run(_gap_handler, days=8)
    ranked = report.ranked_gaps()
    assert ranked == sorted(ranked, key=lambda g: g.situation)


async def test_coverage_grows_with_run_length():
    short = await _harness().run(_null_handler, days=1, events_per_day=3)
    long = await _harness().run(_null_handler, days=25)
    assert long.catalog_coverage > short.catalog_coverage


async def test_failures_record_the_trap_for_diagnosis():
    """A failure has to carry enough context to act on without a rerun."""
    from ai_bos.simulation.scenarios import SCENARIO_CATALOG

    by_id = {s.scenario_id: s for s in SCENARIO_CATALOG}
    report = await _harness().run(_null_handler, days=4)
    assert report.failures

    for f in report.failures:
        scenario = by_id[f.scenario_id]
        assert f.trap == scenario.trap
        assert f.assertion in scenario.must_hold
        assert f.surface_text.strip()
        assert f.occurred_at is not None


async def test_failures_group_by_scenario():
    report = await _harness().run(_null_handler, days=4)
    grouped = report.failures_by_scenario()
    assert grouped
    assert sum(len(v) for v in grouped.values()) == report.failure_count
    for scenario_id, failures in grouped.items():
        assert all(f.scenario_id == scenario_id for f in failures)


async def test_summary_renders():
    report = await _harness().run(_null_handler, days=5)
    text = report.summary()
    assert "Simulation report" in text
    assert "failures found" in text
