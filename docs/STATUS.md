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

Beyond unfinished wiring, three things are missing by design rather than by
omission — see [DESIGN-NOTES.md](DESIGN-NOTES.md).

1. **No case model.** The system is event-driven, but business processes span
   weeks and carry state. There is nowhere for "awaiting insurance verification,
   day 4 of 10" to live.
2. **No trust ramp.** Autonomy is all-or-nothing. There is no shadow mode, no
   draft-for-approval stage, and no per-capability promotion criteria.
3. **No learning loop.** Layer 6 can score outcomes it is given, but nothing
   generates outcomes, and nothing converts recurring situations into questions
   for the owner.

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
              --
              37 passing
```

Coverage is deliberately concentrated on the constraint layer. Untested code is
mostly code that does not yet run.
