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

- **Agents do not act.** `CommunicationAgent`, `SchedulingAgent` and
  `FinanceAgent` each call the model once and return draft text. None calls
  `ToolExecutor`. The loop never closes.
- **Memory is never populated.** `MemoryStore.write_fact` is implemented and
  correct, but no code path calls it during operation.
- **Tools are registered, never invoked.** `bootstrap.py` registers five tools;
  no agent resolves one from the registry.
- **`VectorMemory` assumes a running ChromaDB** on localhost:8000 and has no
  degraded path if it is absent.
- **Calendar tools are stubs.** `BookAppointmentTool` returns a synthetic
  confirmation without touching a real calendar.
- **Delivery confirmation is one-directional.** Sends are marked
  `EXECUTED_UNVERIFIED`; the SendGrid and Twilio webhook receivers that would
  promote them to `CONFIRMED` do not exist.
- **No Alembic revision has been generated.** `alembic/env.py` is configured but
  `alembic/versions/` is empty; `bootstrap.py` uses `create_all` instead.

## Known structural gaps

Beyond unfinished wiring, these are missing by design rather than by omission —
see [DESIGN-NOTES.md](DESIGN-NOTES.md).

1. ~~**No case model.**~~ **Done** — `ai_bos/cases/`. Durable state with
   next-action deadlines, validated transitions, and an advance-every-open-case
   cycle. Mechanics are business-agnostic; case types are supplied by a vertical
   pack (`cases/verticals/healthcare.py`). Not yet wired to the orchestrator.
2. **No trust ramp.** Autonomy is all-or-nothing. There is no shadow mode, no
   draft-for-approval stage, and no per-capability promotion criteria.
3. **No learning loop.** Layer 6 can score outcomes it is given, but nothing
   generates outcomes, and nothing converts recurring situations into questions
   for the owner. The case model now supplies half of this — `BLOCKED` cases
   carry `missing_facts` — but nothing consumes them yet.
4. **The scenario catalog is not vertical-agnostic.** The simulation *engine*
   is (clock, personas, generator, harness all industry-neutral), but
   `simulation/scenarios.py` hardcodes dental content. About half the catalog is
   universal — prompt injection, opt-out, misdirected messages, compound
   requests, ambiguous dates. It should split into a universal core plus
   pluggable vertical packs, mirroring what `cases/verticals/` already does.

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
tests/simulation 39  clock, personas, catalog, generator, harness
tests/cases      37  states, definitions, store, engine
                 ---
                 113 passing
```

Coverage is deliberately concentrated on the constraint layer. Untested code is
mostly code that does not yet run.
