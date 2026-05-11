"""Soul-2 plan-then-execute wrapper for S2 runs (ADR-007).

The wrapper rewrites the user's prompt so the model produces:
1. A 3-bullet plan,
2. A 2-sentence self-critique of the plan,
3. The actual answer.

All in a single round-trip (no extra API call, no extra latency floor).

The wrapper is **opt-in** via settings.SOUL_PLAN_THEN_EXECUTE_ENABLED. Off
by default because Opus already reasons well on most tasks and forcing a
plan section can feel verbose for short prompts. Turn it on for agents
that produce code edits or critical decisions where you want the plan
visible in the run log.
"""
from __future__ import annotations

import re


_WRAPPER_TEMPLATE = """You are handling a deliberate (System 2) request. Before answering, you will think aloud in a short, structured way so the user can audit your reasoning.

Produce three sections **in this order, with these exact headings**:

## Plan
- Bullet 1: the first concrete step you will take.
- Bullet 2: the second step.
- Bullet 3: the third step. Include the assumption you are least sure about.

## Critique
Two sentences. What could go wrong with the plan? What would change your mind?

## Answer
The actual response the user asked for. This section is the one shown to the user as the primary reply. Be direct here; the plan/critique sections are scaffolding above the answer.

If the request is trivial (a greeting, a one-liner, a yes/no) you may skip Plan and Critique and answer directly under ## Answer. Use judgement.

---

USER REQUEST:
{prompt}
"""


def wrap_prompt_for_s2(prompt: str) -> str:
    """Return the S2-wrapped version of the prompt."""
    return _WRAPPER_TEMPLATE.format(prompt=(prompt or "").strip())


_ANSWER_RE = re.compile(r"^##\s*Answer\s*\n", re.MULTILINE | re.IGNORECASE)


def extract_final_answer(text: str) -> str:
    """Pull the ## Answer section out of a plan-then-execute response.

    Used by adapters that want to send only the user-facing answer to
    Telegram / Slack while keeping the full plan-critique-answer block in
    the dashboard.

    Returns the original text untouched if no ## Answer header is found —
    so this is safe to call on any model output.
    """
    if not text:
        return text
    m = _ANSWER_RE.search(text)
    if not m:
        return text
    return text[m.end():].strip()
