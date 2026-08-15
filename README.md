# AI-BOS — AI Business Operating System

An owner describes their business. From that point, the AI runs the operation:
handles inbound customer communication, schedules, invoices, tracks compliance,
and escalates only genuine judgment calls.

This repository is the **foundation scaffold** — eight architectural layers with
the safety surface implemented and tested. See
[docs/STATUS.md](docs/STATUS.md) for an honest account of what is load-bearing
and what is still an empty room.

## Quick start

```bash
cp .env.example .env          # fill in API keys
docker compose up             # Postgres, Redis, ChromaDB, API, Celery worker + beat
python scripts/bootstrap.py   # create tables, register tools
python scripts/smoke_test.py  # verify safety gates end to end
pytest                        # 37 tests across all 8 layers
```

Then `POST /business/describe` with a plain-text business description.

## Architecture

| Layer | Package | Responsibility |
|-------|---------|----------------|
| 0 | `config`, `db`, `workers`, `logging_config` | Fail-fast config, async Postgres with soft-delete, Celery + Redis, structured JSON audit log |
| 1 | `memory` | Hybrid ChromaDB + Postgres store. Every read returns a `MemoryResult` carrying confidence, basis, source IDs and staleness — never bare text |
| 2 | `business` | Intake, LLM domain extraction, confidence classification, verification queue, per-vertical profiles |
| 3 | `tools` | `BaseTool` contract and `ToolExecutor`: idempotency, dry-run, post-hoc verification, rollback, circuit breakers |
| 4 | `agents` | Orchestrator event loop, `AgentContext` budget scoping, Redis conflict locks, loop/stall watchdog |
| 5 | `communication` | Identity resolution, TCPA / HIPAA / CAN-SPAM / GDPR gates, delivery tracking |
| 6 | `improvement` | Outcome tracking, pattern recognition, A/B experiments, Goodhart guard, safety bounds |
| 7 | `owner` | Escalation with auto-resolve, encrypted credential vault, weekly digest |

## Design principles

**Constraints live in code, never in prompts.** Compliance gates, budget ceilings
and safety bounds are ordinary functions the agent cannot reason its way past.
An agent that decides to send an SMS without consent still hits a hard `BLOCKED`
from `check_tcpa`.

**No source, no fact.** Knowledge carries provenance. A claim with no supporting
source is capped at `ASSUMED` and is barred from driving action, regardless of
how confident the model sounded. See `memory/anti_hallucination.py`.

**Never assume an action succeeded.** Every side effect is logged before
execution, keyed for idempotency, and verified afterward. Unverified sends are
marked `EXECUTED_UNVERIFIED` until a provider webhook confirms them.

**Escalate rarely, and only for judgment.** Escalation requires that the system
lack the information, that the decision cannot wait, and that being wrong is
costly. Unanswered escalations auto-resolve to the system's recommendation after
four hours; a high escalation rate is treated as a defect.

## Repository layout

```
ai_bos/
  config.py logging_config.py
  db/          models, async session, migrations
  memory/      confidence, provenance, staleness, vector + structured stores
  business/    intake, domain extraction, profiles, verification
  tools/       base contract, executor, registry, rate limiting, integrations
  agents/      orchestrator, base agent, context, conflict resolver, watchdog
  communication/  identity, compliance gates, delivery tracking
  improvement/ outcomes, patterns, experiments, safety bounds
  owner/       escalation, credential vault, digest
  api/         FastAPI routers
tests/         layer0 … layer7
scripts/       bootstrap, smoke test
docs/          architecture status and design notes
```

## Status

37 tests passing. The safety surface is real and exercised. The execution path
is not yet closed — agents currently return drafts rather than dispatching
through the executor. Read [docs/STATUS.md](docs/STATUS.md) before building on
this, and [docs/DESIGN-NOTES.md](docs/DESIGN-NOTES.md) for where the
architecture is heading.
