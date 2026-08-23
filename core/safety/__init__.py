"""Safety layer — the brakes an unattended agent needs.

Rugol runs agents with `permission_mode="bypassPermissions"` and full shell
access, on schedules, with nobody watching. That combination is the whole point
of the product and also its sharpest edge: there is no human to confirm
anything at 8:30 AM.

Credit where it's due: the idea comes from gstack's `/careful` and `/freeze`
skills (github.com/garrytan/gstack, MIT). This is a reimplementation for
Rugol's runtime, not a port — gstack *warns a human before* a destructive
command, and Rugol has no human to warn, so every rule here is a hard deny.
See NOTICE for attribution.
"""
from core.safety.guards import (
    DENY_RULES,
    DenyRule,
    GuardVerdict,
    build_guard_hooks,
    evaluate_bash,
    evaluate_write,
    extra_rules_from_settings,
)

__all__ = [
    "DENY_RULES",
    "DenyRule",
    "GuardVerdict",
    "build_guard_hooks",
    "evaluate_bash",
    "evaluate_write",
    "extra_rules_from_settings",
]
