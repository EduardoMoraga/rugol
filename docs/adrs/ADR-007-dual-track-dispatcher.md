# ADR-007 — Soul-2 Dual-Track Dispatcher (skeleton)

**Status:** Draft · 2026-05-10 · Authors: Eduardo Moraga + Claude (Opus 4.7)
**Implementation status:** **Not implemented.** Design only. See ADR-006 for
the full Soul Layer plan and ADR-008 for the third sprint.

## Context

Soul-1 (ADR-006) pays a non-trivial token cost on every run: ~600-1500
extra tokens of identity + auto-memory rules + memory block. On Haiku
this is cents; on Opus it adds up. More importantly, **not every request
the user sends deserves an Opus answer**. "Hola, cómo estás" should not
cost the same as "diseña la arquitectura del archivo evolutivo".

Kahneman's dual-process theory frames the move:

- **System 1** — fast, intuitive, parallel, cheap. The right cognitive
  mode for routine recall, restatement, light reformatting, casual
  conversation.
- **System 2** — slow, sequential, deliberate, expensive. Reserved for
  reasoning, multi-step planning, code edits, creative work, anything
  where being wrong has real cost.

A frontier agent platform should pick the right cognitive mode for the
incoming request, not the user. Today Rugol has `model_override`
which lets a caller force "fast" (Haiku) or "deep" (Opus), but the
*decision* is on the caller. The platform itself is dumb.

## Decision (when implemented)

Insert a **classifier step** before model invocation. It runs on Haiku
(the cheapest viable model), takes the prompt + the agent's identity
block + a 2-sentence summary of recent memory, and returns:

```
{
  "track": "s1" | "s2",
  "confidence": 0.0..1.0,
  "rationale": "single sentence why"
}
```

The dispatcher then routes:

- **S1 path**: Haiku, prompt caching enabled on the identity + memory
  + auto-memory blocks (these are stable across requests for the same
  agent), no plan step. Target latency < 2s.
- **S2 path**: Opus 4.7 (or whatever the agent's default is), with an
  optional **plan-then-execute** wrapper that asks the model to write a
  3-bullet plan first and self-critique it before executing. Target
  quality first, latency second.

The classifier itself is cacheable when the prompt structure is
recognisable (e.g. a fixed schedule firing). For ad-hoc Telegram or
dashboard prompts, every classification is a fresh call.

### When to override the classifier

- `model_override="fast"` from the caller → force S1.
- `model_override="deep"` from the caller → force S2.
- Reflection runs → always S2 (they're rare and important).
- Devil's advocate runs → always S2 (already opted-in by the user).

## Tradeoffs

### Positive

- Cost amortisation: most messages are S1 (cheap). The ones that aren't
  pay Opus pricing for a clear reason.
- Latency: S1 with cached prompt is ~2s end-to-end versus ~8-15s for
  Opus deep work. Users feel the difference on routine queries.
- Discipline: the agent that asks "did I really need Opus for this?"
  before every answer ends up cheaper *and* sharper.

### Negative

- Misclassification cost. A query that should have gone S2 but was
  routed S1 produces a worse answer. Mitigations: track classifier
  agreement against user feedback (thumb-up/down on each run) and
  retrain the classifier prompt over time.
- One extra model call per run. On a 5¢ Haiku classifier this is
  noticeable only at very high volume.
- More moving parts. The dashboard needs an S1/S2 indicator on each
  run for transparency.

## Implementation surface (when built)

New files:
- `core/soul/dispatcher.py` — classifier prompt + routing logic.
- `core/soul/cache.py` — prompt-cache wrapper for S1 path (uses Anthropic's
  native prompt caching headers).
- `core/soul/plan_then_execute.py` — wrapper for S2 path.

Modified:
- `core/runner/orchestrator.py` — call dispatcher before `_execute`.
- `core/runner/claude_runner.py` — accept `track` parameter, configure
  prompt caching on system prompt blocks.
- `core/db/models.py` — `Run` row gains `track: str` (s1 | s2).
- `dashboard/src/components/runs/RunCard.tsx` — show track badge.

Telemetry to add:
- `run.track`, `run.classifier_confidence`, `run.classifier_rationale`.
- Aggregate panel: % S1 vs S2 per agent, cost saved by routing.

## Open questions

- Should the classifier be a separate `core/soul/classifier-agent` so its
  own evolution archive (ADR-008) can improve it over time? Likely yes —
  a self-improving classifier is exactly what makes the dispatcher
  durable.
- How to handle ambiguous prompts? Confidence < 0.6 → default to S2
  (err on quality), or → ask the user "fast or deep?".
- Streaming: S1 should stream tokens; S2 with plan-then-execute can't
  start streaming until the plan is finalized. Dashboard UX needs both.

## Decision deferred until

Soul-1 has shipped, agents are actively using `save_memory`, and we
have enough run telemetry to know which prompts users send most.
Without that data, the classifier prompt is a guess.
