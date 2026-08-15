# Design notes

Where the architecture is heading, and why it differs from what is currently
committed. These conclusions came out of reviewing the scaffold against the
actual problem.

## 1. "Describe your business once" is the wrong premise

Nobody can usefully answer *"tell me everything about your business."* The
knowledge is tacit and situational; it surfaces only when a specific case
arises. The same owner who writes a useless three-sentence description can
answer *"a patient just asked about payment plans — do you offer those?"* in
four seconds.

**Direction:** invert the intake. Start with near-zero knowledge in shadow mode
and let real events generate the questions. Facts then arrive with concrete
provenance attached, and the owner's effort is spread thin rather than
front-loaded into a form they will abandon.

## 2. The unit of work is a case, not an event

The current orchestrator is event-driven: message arrives, agent handles it,
done. But operations run as processes with state spanning weeks:

```
inquiry → insurance verified → booked → reminded → seen
        → claim filed → paid → recall scheduled
```

Dozens run concurrently, each advancing on its own clock. Event-driven agents
structurally cannot hold this — there is nowhere to record "waiting on the
insurer, day 4 of 10."

**Direction:** a durable case model with explicit state and next-action
deadlines. The system's job each cycle becomes *advance every open case*. This
is closer to a workflow engine with model-driven decision points than to a chat
agent. `MessageThread` gestures at this; it is not sufficient.

## 3. Autonomy is a ramp, and the ramp is the product

No owner grants full autonomy on day one. Trust level should be a first-class
property **per capability**, never global:

| Stage | Behavior |
|-------|----------|
| Shadow | Decides everything, sends nothing, logs what it would have done |
| Draft | Drafts, owner approves with one click |
| Auto-with-recall | Sends, with an undo window and a live feed |
| Auto | Sends, surfaced in the weekly digest |

Promotion must be mechanical and auditable — *"appointment confirmations promote
to Auto after 50 consecutive approvals with zero edits."* Reminders might reach
Auto in a week; anything touching money or PHI may never leave Draft, and that
is a feature rather than a limitation.

## 4. Simulation teaches what to ask; only reality teaches what is true

Without a live business there is no event volume, and a case engine is
untestable without volume. The answer is a simulator that produces a realistic
inbound stream — weeks of messages, plausible arrival times, recurring customers
with continuous histories.

It must be **adversarial rather than friendly**. Generate the mess: someone
texting from an unrecognized number, a request contradicting a policy stated
three weeks ago, two family members sharing an email address, a reschedule
arriving after the appointment already passed, anger about something predating
the system.

**The partition that matters:** a simulated patient asking about payment plans
is real evidence that payment plans are a *question type* needing a standing
answer. It is zero evidence about whether this clinic offers them. Facts learned
in simulation must therefore live in a **separate memory namespace** that
production never queries — not merely a lower confidence tier, since every tier
has some upgrade path. Confidence answers *how much do I trust this?*; this is a
different axis: *is this about a real entity at all?*

**Echo-chamber caveat:** if the same model generates inbound traffic and handles
it, the system looks brilliant because the test data is drawn from exactly the
distribution it expects. Seed scenarios from real sources — review sites,
complaint boards — rather than from imagination. And treat simulated frequency
as establishing only that *a situation type exists*; only real traffic
establishes proportions.

## 5. Three learning loops worth building

1. **Gap ledger.** Every unresolved situation writes a row: what happened, what
   the system needed to know, what it did instead, how often this recurs. After
   a simulated month this is a ranked interview script grounded in specifics —
   the mechanism that makes having no customer productive rather than blocking.
2. **Policy induction.** After N similar cases, propose a standing policy rather
   than ask an open question: *"I have drafted 17 responses to payment-plan
   questions and keep converging on this one — should it become standard?"*
3. **Case-routing feedback.** Did an insurance question correctly become a case
   that parks awaiting verification, or was it closed prematurely? Fully
   learnable in simulation, since it concerns the system's own mechanics.

## 6. What to cut

**Layer 6, for now.** The Goodhart guard and experiment manager need at least 20
samples and 20% traffic splits. A small clinic generates roughly 30 inbound
messages a week — months per experiment, spent optimizing before basic execution
is established. It solves a year-three problem. The trust ramp's approval-rate
data is the feedback signal that matters at this stage.

**The generic-business ambition.** A dental clinic and a landscaping company
share almost nothing operationally. Horizontal means never getting deep enough
to be more than a better autoresponder. Go vertical — and choose the vertical by
**integration tractability, not market size**. The question is not where the TAM
is, but whose system-of-record exposes an API you can obtain a key for today.
Open Dental has a real REST API; Dentrix effectively does not. That is a better
reason to pick dental than dentists having money.

**Tier-2 integrations, until there is a design partner.** Without an operator to
explain what the practice management system means in daily use, you would be
coding against API semantics you do not understand. Put the system-of-record
behind an interface, back it with the simulator, and swap in the real one later.

## Revised build order

1. Case model — durable state, next-action deadlines, advance-every-case cycle
2. Simulator and replay harness — makes everything above testable
3. Shadow log and gap ledger — the readable record of decisions and unknowns
4. Trust ramp — per-capability stages with mechanical promotion
5. Close the executor loop — agents dispatch through `ToolExecutor` rather than
   returning drafts
6. Provider webhooks — promote `EXECUTED_UNVERIFIED` to `CONFIRMED`

## The deliverable, reframed

With no design partner, the thing being built is not a product — it is the
artifact that earns one. A month of shadow-mode transcript for a business type,
showing what the system would have done, where it asked for help, and where it
was wrong, persuades a skeptical owner far more than a demo they have no reason
to trust.

That reframe determines what deserves polish: **the log has to be readable by a
practitioner, not a developer.**
