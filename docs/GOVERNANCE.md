# Creator and instance

Two systems exist: the **creator** (the platform) and the **instances** it
creates for individual businesses. When an instance needs something new after
creation, who decides?

Neither extreme works. Fully self-maintaining instances are dangerous and
fragment the only durable advantage the platform has. Fully on-demand makes
the creator a bottleneck that caps the fleet at a handful of businesses.

The seam runs along **what kind of thing is changing**.

## The three tiers

| Tier | Who decides | Examples |
|------|-------------|----------|
| **LOCAL** | Instance, alone | Facts, policy values, party and booking data, service catalog, trust record |
| **PROPOSED** | Instance drafts, creator ships | New case types, newly observed failure patterns, capability requests, vertical packs |
| **PLATFORM** | Creator only | Engine code, tool code, compliance rules, trust policy, safety bounds |

Enforced in `ai_bos/platform/tiers.py`. Every `ChangeKind` maps to exactly one
tier, and a test asserts the mapping is total.

## Why this split rather than a preference

**Learning economics.** If instances self-maintain, each learns only from its
own experience — 100 businesses means 100 systems carrying 1/100th of the
available knowledge. If discoveries flow up and improvements flow down, each
carries the whole fleet's experience. The durable advantage is *the accumulated
record of things going wrong and being fixed*, and that only compounds when
pooled. Self-maintaining instances shatter it.

**Safety.** A business system that can rewrite its own compliance gate has no
compliance gate. Platform-tier changes are not merely denied to an instance —
they are **inadmissible**, so a confused or compromised instance has no channel
through which to ask for its own safety rules to be relaxed.

## The tension, and how it resolves

Tier 3 protects safety; Tier 1 protects speed. The resolution is to **push as
much as possible into data**, so instances adapt broadly without ever modifying
code. A new case type should be a row, not a deploy. This is why the
vertical-pack-as-data pattern runs through the whole codebase:

```
cases/verticals/         case types and deadlines
simulation/scenarios/verticals/   failure patterns
domain/verticals/        services, resource types, coding systems
```

The more expressive the data model, the less an instance needs code it is not
allowed to write.

## What travels between instances

**Patterns travel. Records never do.**

- *Pattern*: "businesses of this type are asked about payment plans" — shareable
- *Record*: "this named person asked on Tuesday" — never leaves the instance

`platform/federation.py` strips identifiers **on ingest** rather than trusting
the sender, so an instance cannot opt into leaking records by mislabelling
them. Emails, phone numbers, national identifiers and street addresses are
redacted before a submission is stored.

A pattern also requires **independent corroboration from at least three
distinct businesses** before the fleet acts on it. One business reporting the
same thing fifty times still counts once — a single business's quirk is not a
fleet-wide truth.

## How this shows up elsewhere

The gap ledger is already a Tier 2 mechanism: it detects that a fact is
missing and *drafts a question*, rather than inventing an answer. The trust
ledger is Tier 1: authority is earned locally and is deliberately
non-transferable, because it is evidence about this instance in this business.
