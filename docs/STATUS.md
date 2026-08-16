# Implementation status

An honest account of what is load-bearing and what is scaffolding, so nobody
builds on an empty room by mistake.

## What is real

These are implemented, tested, and behave correctly under adversarial input.

| Component | File | Verified by |
|-----------|------|-------------|
| Confidence gating | `memory/confidence.py`, `business/confidence.py` | `tests/layer1`, `tests/layer2` |
| Anti-hallucination downgrade | `memory/anti_hallucination.py` | `tests/layer1` |
| TCPA consent gate | `communication/compliance/tcpa.py` | `tests/layer5` |
| HIPAA PHI + channel gate | `communication/compliance/hipaa.py` | `tests/layer5` |
| CAN-SPAM gate | `communication/compliance/can_spam.py` | `tests/layer5` |
| Idempotency key derivation | `tools/base.py` | `tests/layer3` |
| Budget scoping on child agents | `agents/context.py` | `tests/layer4` |
| Immutable-component bounds | `improvement/safety_bounds.py` | `tests/layer6` |
| Escalation auto-resolve | `owner/escalation.py` | `tests/layer7` |

A useful pattern in that list: **every one of them says no.** The constraint
layer is complete. The generative layer is not.

## What is scaffolding

Correct in shape, not yet wired to anything.

- **`SchedulingAgent` and `FinanceAgent` still only draft.**
  `CommunicationAgent` now closes the loop — it drafts, dispatches through
  `ToolExecutor`, and settles its cases on the result. The other two have not
  been converted.
- **Memory is never populated.** `MemoryStore.write_fact` is implemented and
  correct, but no code path calls it during operation.
- **Tools are registered, never invoked.** `bootstrap.py` registers five tools;
  no agent resolves one from the registry.
- **`VectorMemory` assumes a running ChromaDB** on localhost:8000 and has no
  degraded path if it is absent.
- **Calendar tools are stubs.** `BookAppointmentTool` returns a synthetic
  confirmation without touching a real calendar.
- **Webhook receivers exist but are unproven against live traffic.**
  `api/routers/webhooks.py` settles SendGrid and Twilio events and verifies
  Stripe signatures. The action lookup scans unverified rows rather than
  querying by provider id — correct but not indexed for volume.
- **No Alembic revision has been generated.** `alembic/env.py` is configured but
  `alembic/versions/` is empty; `bootstrap.py` uses `create_all` instead.

## Known structural gaps

Beyond unfinished wiring, these are missing by design rather than by omission —
see [DESIGN-NOTES.md](DESIGN-NOTES.md).

1. ~~**No case model.**~~ **Done** — `ai_bos/cases/`, wired to the
   orchestrator. Durable state with next-action deadlines, validated
   transitions, and an advance-every-open-case cycle that now runs on the
   orchestrator's idle tick. Mechanics are business-agnostic; case types come
   from a vertical pack (`cases/verticals/healthcare.py`).
2. ~~**No trust ramp.**~~ **Done** — `ai_bos/trust/`. Four stages per
   capability with mechanical promotion, ceilings that pin money and regulated
   data below full autonomy permanently, and demotion on rejection. Enforced
   inside `ToolExecutor`, so an agent never sees the decision.
3. ~~**No learning loop.**~~ **Partly done** — `improvement/gap_ledger.py`
   turns `BLOCKED` cases into a ranked owner interview script. Outcome
   generation from real sends is still missing.
4. ~~**The scenario catalog is not vertical-agnostic.**~~ **Done** —
   `simulation/scenarios/` now splits into a 15-scenario universal core and
   vertical packs (`scenarios/verticals/healthcare.py`, 4 scenarios). Catalogs
   are instances, so one process can simulate two verticals at once.

## Simulation results

Same 227-event stream, seed 0, 20 days — stateless handler versus one with
durable case state:

| Scenario | stateless | case-aware |
|----------|----------:|-----------:|
| `routing.compound_request` | 28 | **0** |
| `temporal.dormant_thread_revival` | 12 | **0** |
| `knowledge.policy_not_on_record` | 36 | 12 |
| `temporal.reschedule_after_the_fact` | 26 | 18 |
| `compliance.phi_over_plain_email` | 16 | 16 |
| `adversarial.prompt_injection` | 24 | 24 |
| `identity.shared_household_email` | 20 | 20 |

The last three are the control: the case model does not address compliance or
identity, and correctly changes nothing there. The two partial results are
honest rather than mysterious — `policy_not_on_record` asserts three properties
and the handler implements two, and `reschedule_after_the_fact` needs a prior
appointment case that does not exist for personas appearing early in the run.

Reproduce with `python scripts/run_case_simulation.py --days 20`.

## Test coverage

```
tests/layer0  3   config, logging
tests/layer1  9   confidence, anti-hallucination
tests/layer2  3   business confidence classification
tests/layer3  2   idempotency
tests/layer4  3   agent context budget inheritance
tests/layer5  9   TCPA, HIPAA, CAN-SPAM
tests/layer6  6   Goodhart guard, safety bounds
tests/layer7  2   escalation
tests/simulation 48  clock, personas, catalog split, generator, harness
tests/cases      57  states, definitions, store, engine, orchestrator, gap ledger
tests/trust      38  stages, policy, ledger, gate, executor gating, webhooks
                 ---
                 178 passing
```

Coverage is deliberately concentrated on the constraint layer. Untested code is
mostly code that does not yet run.
