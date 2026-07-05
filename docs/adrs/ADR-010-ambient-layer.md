# ADR-010 — Ambient Layer (codename *Atalaya*): proactive perception & initiative

**Status:** Accepted · 2026-06-29 · Authors: Eduardo Moraga + Claude (Opus 4.8)

## Context

Through v0.6 Rugol grew a real brain and a real body:

- **Brain (Soul Layer, ADR-006/007/008/009)** — every *run* is now smart.
  It reads persistent memory, knows the real date, sounds like itself, routes
  itself S1/S2 (Kahneman, ADR-007), reflects on its own spec (ADR-008), and
  shares context across agents (Honcho, ADR-009).
- **Body (core scheduler/orchestrator/adapters)** — runs are queued,
  concurrency-bounded, streamed, persisted, and reachable from Telegram and
  Slack.

But there is a hole, and a user surfaced it precisely:

> "Todo lo que he aprendido y aplicado de IA con agentes había sido
> unidireccional con condiciones. Hoy, si yo no le digo qué hacer, a qué hora,
> y a qué hora recibir de vuelta el output, no pasa nada. No veo realmente el
> comportamiento agéntico. Me imagino un agente lanzando procesos en segundo
> plano para revisar carpetas, MCP, lo que fuera, y generando output de manera
> constante para advertir, sugerir, prevenir."

Every run today is triggered by **a cron a human wrote** (fixed time, fixed
prompt) or **a message a human sent** (reactive). The cron gives the *appearance*
of autonomy but it is just a timer the human pre-decided. Nothing in Rugol
**observes the world on its own and decides, by its own judgment, that something
is worth the user's attention.** The brain is excellent at answering; nobody asks.

### The thesis this ADR commits to

Three claims frame the whole design. They were argued at length before this ADR
and are stated here as the load-bearing assumptions:

1. **The loop is not the hard part.** A daemon that polls sources every N minutes
   and decides whether to speak is a weekend of code (we already run one — the
   voice-sync `IntervalTrigger` job in `scheduler.py`). The frontier is not
   *autonomy*, it is **judgment under uncertainty**: knowing that the email from
   Camila matters and the other four do not, *without being told the filter.*

2. **Proactivity has an asymmetric cost.** A *reactive* agent at 80% precision is
   useful — the user asked, the user verifies, the misses are free. A *proactive*
   agent at 80% precision is spam — it interrupts wrongly 1 in 5 times and gets
   muted within a week. In IR terms: a reactive agent may run at high recall and
   low precision; **a proactive agent must run at high precision**, accepting
   lower recall, because a false positive costs trust and trust does not
   replenish. This single asymmetry dictates the entire architecture.

3. **"Incremental learning" is a memory architecture, not model weights.** The
   model is frozen. What learns is the structure around it: a living model of the
   user plus a feedback loop that captures their reactions and folds them back
   into relevance. Rugol already has the substrate (per-agent file memory +
   ontology graph). The Ambient Layer closes the loop.

### Why this is defensible (why the big platforms won't eat it)

The obvious objection — "Anthropic/Microsoft/Google will ship this with a nicer
UI" — cuts against the *configuration* layer (which they will commoditize), not
against this layer. A massive platform builds for the median user, cannot ingest
one person's fragmented stack (Outlook + Gmail + Notion + Asana + WhatsApp +
local folders) with the depth required to model *them*, and **cannot ship the
error rate that proactivity tolerates only when it is personal**. An always-on
loop is expensive for a platform (millions of users × constant polling) and cheap
for one person (cents/day, §"Cost model"). The individual builder has the edge
here, not the disadvantage. This layer is Rugol's *soul made outward-facing* —
the part that is hard to copy because it is hard to make personal.

## Decision

Rugol gains a `core/ambient/` module — the **Ambient Layer**, codename
**Atalaya** ("watchtower": it watches your world and calls out only what
matters). It sits *above* the orchestrator and reuses the entire Soul Layer for
free. It introduces nothing the brain already does; it only adds **perception**
and **initiative**.

### The pipeline (six stages)

```
                        ┌─────────────────────────────────────────────┐
   SOURCES              │            core/ambient/                     │
   (MCP, files, web)    │                                              │
        │               │   1. SENSE      cheap pollers, no LLM        │
        ▼               │      └─► Observation rows (deltas only)      │
   ┌──────────┐         │                                              │
   │ gmail    │────────►│   2. SCORE      Haiku salience pass          │
   │ calendar │         │      └─► reads user-model (memory+ontology)  │
   │ asana    │         │          emits salience + urgency            │
   │ slack    │         │                                              │
   │ files    │         │   3. GATE       fail-closed, two-tier        │
   │ youtube  │         │      ├─► SUPPRESS (most of them)             │
   │ pipeline │         │      ├─► DIGEST   (pooled, low stakes)       │
   │ (HRO/CRM)│         │      └─► INTERRUPT(rare, high bar, budgeted) │
   └──────────┘         │                                              │
                        │   4. SYNTHESIZE enqueue a normal Rugol run   │
                        │      └─► agent drafts msg + suggested action │
                        │          (gets soul/memory/dispatcher free)  │
                        │                                              │
                        │   5. DELIVER    Telegram/Slack + buttons     │
                        │      └─► 👍 útil · 👎 ruido · 😴 luego · 🔕  │
                        │                                              │
                        │   6. LEARN      feedback → memory + weights  │
                        │      └─► per-scope relevance tuning          │
                        └─────────────────────────────────────────────┘
```

The user's WhatsApp dream maps directly:

| User's example | Sensor | Tier | Suggested action |
|----------------|--------|------|------------------|
| "Tienes 5 correos, uno de Camila es importante; acá la respuesta" | `gmail` | INTERRUPT | draft reply |
| "Se generaron 4 postulaciones, un candidato es muy bueno" | `pipeline` (HRO) | DIGEST→INTERRUPT if score high | open candidate |
| "Este canal subió un video interesante" | `youtube` | DIGEST | link + 2-line why |
| "Revisé tus archivos y surgió una idea" | `files` | DIGEST | propose note/task |

### Stage 1 — SENSE (no LLM, cheap, idempotent)

A **Sensor** is a small async poller that, on each tick, fetches *deltas since its
last cursor* from one source and normalizes them into `Observation` rows. Sensors
never call an LLM — burning a model on every poll is the cost mistake that makes
"always-on" look expensive. They are the substrate, not the value.

```python
class Sensor(Protocol):
    name: str                 # "gmail", "asana", "files", ...
    default_interval_s: int   # poll cadence
    async def poll(self, cursor: str | None) -> tuple[list[ObservationDraft], str]:
        """Return (new observations, new cursor). Pure I/O + normalization."""
```

Sensors reuse what Rugol/eduagent-gateway already wire: MCP servers (Gmail,
Calendar, Slack, Asana, Notion via the SDK), the filesystem, and HTTP for RSS/
YouTube. `external_id` per observation gives O(1) dedup so the same email is never
surfaced twice (mirrors the `conversation_id` idempotency trick already used in
`PipelineItem`). Bundled Phase-0/1 sensors: `gmail`, `calendar`, `asana`,
`files`, `youtube`, `pipeline` (reads the existing `pipeline_items` table — HRO
candidates / CRM leads already flow there).

### Stage 2 — SCORE (the judgment filter)

For each `new` observation, a **salience scorer** runs — the *same pattern* as the
Soul-2 dispatcher (`core/soul/dispatcher.py`): a Haiku call with a fixed,
cacheable system prompt, fail-closed on parse error. It receives the observation
plus the **user model** (the persistent memory block + the relevant slice of the
ontology people/topic graph) and returns:

```json
{ "salience": 0.0..1.0, "urgency": "now" | "today" | "whenever",
  "scopes": ["sensor:gmail", "person:camila", "topic:hro"],
  "why": "one sentence" }
```

`salience` is "how much would Eduardo care", judged against *his* model, not a
generic one. `scopes` are the tags the feedback loop later tunes (Stage 6). The
scorer is deliberately cheap and deliberately *humble*: when unsure it returns low
salience. Missing a real signal is recoverable (it resurfaces, or shows in the
digest); crying wolf is not.

### Stage 3 — GATE (the asymmetric-cost mechanism — the crux)

This is where claim #2 becomes code. The gate is **fail-closed** (default = stay
quiet) and **two-tier**, with a hard interrupt budget and quiet hours:

```python
def decide(obs, weights, budget, clock) -> Literal["interrupt","digest","suppress"]:
    # weighted score: learned per-scope multipliers (Stage 6) bend the raw score
    score = obs.salience * weights.product_for(obs.scopes)   # e.g. person:camila ↑

    if score < settings.AMBIENT_DIGEST_FLOOR:        # ~0.35 — most observations
        return "suppress"

    interrupt_ok = (
        obs.urgency == "now"
        and score >= settings.AMBIENT_INTERRUPT_BAR  # ~0.80 — deliberately high
        and budget.interrupts_left() > 0             # hard daily cap (default 5)
        and not clock.in_quiet_hours()               # e.g. 22:00–07:30 America/Santiago
    )
    return "interrupt" if interrupt_ok else "digest"
```

Why two tiers solve the asymmetry:

- **INTERRUPT** = push *now*. Rare, high bar, budgeted. A wrong interrupt is the
  expensive failure, so the bar is high and the daily count is capped — even a
  mis-scoring model physically cannot flood the user.
- **DIGEST** = pooled into a scheduled summary (morning/evening — reuse the
  existing cron mechanism, the digest *is* a normal scheduled agent run). A
  digest miss is cheap: the user skims past one bad line. So the bar is low, and
  recall lives here. **The digest is the pressure-release valve that lets the
  interrupt bar stay ruthless.**

### Stage 4 — SYNTHESIZE (reuse the orchestrator wholesale)

A surviving observation does **not** get hand-formatted by the ambient module.
The module **enqueues a normal Rugol run** with a new source tag:

```python
await get_orchestrator().enqueue(RunRequest(
    agent_name="atalaya",          # a bundled ambient agent (see templates)
    prompt=render_brief(obs),      # "Surfaced: <obs>. Draft the message + 1 action."
    source="ambient",              # new source value (String(16) fits)
    metadata={"observation_id": obs.id, "tier": tier},
))
```

This is the highest-leverage decision in the ADR: synthesis inherits **the whole
Soul Layer for free** — identity, persistent memory, world-state date, S1/S2
routing, auto-memory checkpoint, even the devil's-advocate option for high-stakes
interrupts. The ambient module writes *zero* prompt-engineering of its own beyond
a thin brief template. The synthesis run produces the message text *and* an
optional structured `suggested_action` (draft reply, propose Asana task, open
candidate) the user can one-tap accept.

### Stage 5 — DELIVER (reuse the adapters)

The run's `final_text` is delivered through the existing Telegram/Slack adapters
with inline feedback buttons (Telegram already supports inline keyboards in
`adapters/telegram.py`). Each delivered message becomes a `Signal` row.
WhatsApp — the user's stated target channel — is a Phase-3 adapter (Meta Cloud
API or Twilio); Telegram/Slack ship first because they are already wired.

### Stage 6 — LEARN (close the loop — claim #3 as code)

Every signal carries lightweight feedback affordances and implicit signals:

- **Explicit**: 👍 útil · 👎 ruido · 😴 luego (snooze) · 🔕 nunca de esta fuente.
- **Implicit**: did the user tap the suggested action? open the link? reply to the
  draft? ignore it until it expired?

Feedback updates two stores:

1. **Per-scope `RelevanceWeight`** — `person:camila` 👍 nudges its multiplier up;
   `topic:newsletters` 👎 nudges it down. This is the fast, legible learning that
   bends Stage 3 the very next tick (EWMA update, bounded to e.g. [0.2, 3.0]).
2. **Persistent memory** — strong/repeated signals are written as durable
   memories via the existing `save_memory` path ("Eduardo marca como ruido los
   correos de proveedores X"), so the *scorer's* user model improves too.

A periodic **reflection** (reuse `improvements/reflector.py` pattern) reviews the
last K signals and proposes threshold/weight adjustments **for human approval** —
no silent self-tuning of what is allowed to interrupt a person.

## The core principle, stated once

> **Default quiet. Earn every interruption. Make the cheap channel (digest) carry
> recall so the expensive channel (interrupt) can demand precision. Let feedback —
> not the engineer — set the thresholds over time.**

Everything in this ADR is downstream of that sentence.

## Cost model

For **one** user the economics invert the "always-on is expensive" intuition:

| Stage | Model | Volume/day | ~Cost/day |
|-------|-------|-----------|-----------|
| Sense | none (I/O) | ~hundreds of polls | $0 |
| Score | Haiku, cached system prompt | ~30–80 observations | a few cents |
| Synthesize | Sonnet (Opus for high-stakes interrupts) | ~3–10 survivors | cents–low $ |
| Digest assembly | one Sonnet run ×1–2/day | 1–2 | cents |

Order of magnitude: **a few dollars a month** for a personal deployment. Tiered
routing (Haiku scores, Sonnet/Opus synthesize) is what keeps it there — the same
discipline ADR-007 applied to chat, now applied to perception.

## Data model (proposed — additive, no migration of existing tables)

New SQLAlchemy models in `core/db/models.py` (auto-created by `create_all`; the
idempotent column-add migrator handles later evolution):

```python
class Observation(Base):           # raw perception
    id; sensor: str; external_id: str       # UNIQUE(sensor, external_id) — dedup
    kind: str                                # email|event|task|message|video|file
    title: str; summary: str; payload: JSON
    observed_at; salience: float|None; urgency: str|None
    scopes: JSON|None                        # ["person:camila","topic:hro"]
    state: str  # new|scored|surfaced|suppressed|expired
    created_at

class Signal(Base):                # a thing actually shown to the user
    id; observation_id -> observations.id
    tier: str  # interrupt|digest
    channel: str  # telegram|slack|whatsapp
    agent_name: str; run_id -> runs.id|None
    message_md: str; suggested_action: JSON|None
    state: str  # queued|delivered|acted|dismissed|snoozed|expired
    delivered_at|None; created_at

class SignalFeedback(Base):        # the learning signal
    id; signal_id -> signals.id
    kind: str  # useful|noise|snooze|never|acted|opened|ignored
    note: str|None; created_at

class RelevanceWeight(Base):       # the legible, fast-learning memory
    id; scope: str   # UNIQUE — "sensor:gmail" | "person:camila" | "topic:ia"
    weight: float (default 1.0)    # bounded multiplier, EWMA-updated
    updated_by: str  # feedback|reflection|user
    updated_at

class SensorState(Base):           # incremental polling cursors
    id; sensor: str  # UNIQUE
    cursor: str|None; enabled: bool (default True); config: JSON|None
    last_run_at|None
```

## Implementation surface

New files:
- `core/ambient/__init__.py`
- `core/ambient/observation.py` — `ObservationDraft` dataclass + persistence
- `core/ambient/sensors/base.py` — the `Sensor` protocol + registry
- `core/ambient/sensors/{gmail,calendar,asana,files,youtube,pipeline}.py`
- `core/ambient/scorer.py` — salience pass (clone of `soul/dispatcher.py` shape)
- `core/ambient/gate.py` — `decide()` (the snippet above) + `InterruptBudget`
- `core/ambient/loop.py` — `register_ambient_jobs(scheduler)`; one
  `IntervalTrigger` per enabled sensor (mirrors `add_voice_sync_job`) + a digest
  cron + a feedback-reflection cron
- `core/ambient/feedback.py` — EWMA weight update + memory write
- `core/api/ambient.py` — REST: list/inspect observations & signals, toggle
  sensors, post feedback (also hit by Telegram button callbacks)
- `agents-templates/atalaya.md` — the bundled ambient synthesis agent
- `tests/test_ambient_gate.py` — the gate is pure logic; unit-test it hard
  (asymmetry invariants: budget cap holds, quiet hours hold, fail-closed holds)

Modified (minimal, surgical):
- `core/db/models.py` — add the 5 models above.
- `core/main.py` — **one wiring line** in the lifespan startup:
  `register_ambient_jobs(get_scheduler())` (guarded by `settings.AMBIENT_ENABLED`,
  default **False** — the layer ships dark and the user opts in).
- `core/config.py` — `AMBIENT_ENABLED`, `AMBIENT_DIGEST_FLOOR`,
  `AMBIENT_INTERRUPT_BAR`, `AMBIENT_MAX_INTERRUPTS_PER_DAY`,
  `AMBIENT_QUIET_HOURS`, per-sensor intervals.
- `core/runner/orchestrator.py` — add `"ambient"` to the source set and to
  `SOUL_AUTO_CHECKPOINT_SKIP_SOURCES` default? **No** — ambient runs *should*
  checkpoint, that is how the user model learns. Add `"ambient"` only to the
  source enum docstring.
- `dashboard/` — an "Atalaya" page: live observation stream (SSE off the bus,
  topics `observation:*` / `signal:*`), per-sensor on/off, the interrupt-budget
  gauge, and a feedback timeline. Empty/loading/value states per the dashboard
  product bar.

Bus topics added: `observation:new`, `observation:scored`, `signal:surfaced`,
`signal:delivered`, `signal:feedback`. The dashboard SSE and any future hook
listen exactly as they do for `run:*`.

## Phasing — "build it on your own life" (this is the validation method)

The only honest way to find where the *judgment* breaks is to run it on the
author's real inbox and tune precision by hand over weeks. The phases are
deliberately a precision-discovery ladder, not a feature checklist.

- **Phase 0 (1 sensor, digest-only, no interrupts).** `gmail` → score → **digest
  to Telegram** once a day. No interrupt tier yet. Goal: measure raw precision on
  one real source with zero blast radius. Ship the gate + scorer + one sensor.
- **Phase 1 (feedback + weights).** Add the buttons and `RelevanceWeight`. Watch
  the noise rate fall as `person:`/`topic:` weights settle. This is where claim #3
  proves itself or doesn't.
- **Phase 2 (interrupt tier + more sensors).** Turn on INTERRUPT with a budget of
  3/day. Add `calendar`, `asana`, `pipeline`, `youtube`, `files`. The Camila case
  goes live.
- **Phase 3 (suggested actions + WhatsApp).** Draft-reply / propose-task /
  open-candidate one-tap actions. Add the WhatsApp adapter.
- **Phase 4 (generative sensor).** The "revisé tus archivos y surgió una idea"
  sensor — periodic synthesis over the workspace + ontology that proposes, not
  just reports. Highest precision bar; ships last, on top of a tuned gate.

## Consequences

### Positive
- Closes the exact gap the user named: Rugol stops being unidirectional. It
  becomes the first thing in the user's stack that *initiates*.
- Reuses ~everything: orchestrator, soul, dispatcher, memory, ontology, adapters,
  bus, scheduler. The net-new surface is one module + 5 tables + one wiring line.
- The defensible part of the product (personal, judgment-rich, proactive) gets a
  home. This is the "soul made outward-facing" — the part platforms won't copy.
- Cheap enough for a personal deployment to run forever.

### Negative
- **Trust is the failure mode, not crashes.** A bad interrupt costs more than a
  bug. Mitigations are structural (fail-closed gate, hard budget, quiet hours,
  digest-first phasing) not just careful coding.
- More always-on machinery → more ways to leak or mis-poll. Sensors touch real
  inboxes; see Privacy.
- Scorer cost scales with observation volume. Mitigation: sensors pre-filter
  cheaply (no LLM) and the scorer is Haiku with a cached prompt.
- Tuning is real work. The thresholds in this ADR are *priors*, not answers; they
  are wrong until Phase 0/1 data corrects them.

### Out of scope
- WhatsApp adapter (Phase 3).
- The generative "idea from your files" sensor (Phase 4).
- Multi-user ambient (this is single-operator by design; the personalness is the
  point).
- Fully autonomous *action* (sending the reply without a tap). Deliberately not in
  scope — the human stays in the loop on anything outbound. The agent proposes;
  the human disposes. Crossing that line is a separate ADR with a much higher bar.

## Privacy & security
- Sensors read real personal data. Observation `payload` may hold email bodies;
  it is stored in the local SQLite only, never sent anywhere except the LLM call
  the user already authorized for that agent. Default retention: prune
  `Observation` rows older than N days (config).
- No secrets in code; all source credentials via the existing MCP/.env wiring.
- The interrupt budget and quiet hours are also a *safety* feature, not only UX —
  they bound worst-case behavior of a mis-scoring model.
- `AMBIENT_ENABLED` defaults **False**. The watchtower is dark until the operator
  lights it.

## Open questions
- **Scorer as its own evolving agent?** Like ADR-007's classifier question: a
  self-improving salience scorer (ADR-008 archive) is probably what makes the
  judgment durable. Likely yes, after Phase 1 gives it training signal.
- **Snooze semantics** — does 😴 re-surface in N hours, or only escalate if
  salience rises? Lean: re-score on next tick, suppress until salience exceeds the
  snoozed level.
- **Cross-sensor correlation** — "Camila emailed *and* a meeting with her is in
  2h" should fuse into one stronger signal. Deferred to post-Phase-2; needs the
  ontology to link entities across sensors first.
- **Confidence < floor but recurring** — a low-salience item seen 5 days running
  may itself be a signal. A "persistence" bump is a Phase-1 candidate.

## Decision deferred until
Nothing — Phase 0 is buildable today against the current codebase. The interrupt
tier (Phase 2) is deferred until Phase 0/1 precision data exists, because turning
on interruptions before the scorer is tuned would burn exactly the trust this ADR
is built to protect.
