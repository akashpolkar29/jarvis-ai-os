"""Classification -> Effect mapping for M2 cloud-egress capability invocations.

Kept separate from ``router.py`` deliberately: this is the one pure
decision ("given this task's real Classification, which ``Effect`` must
a cloud-provider call declare") that ``ModelRouter`` orchestrates
around, matching this project's established split between pure
decision logic (``domain/policy.py``'s ``evaluate()``) and the stateful
orchestration built on top of it (``application/policy/orchestrator.py``'s
``AuthorizationOrchestrator``).

**A real, forced consequence of the already-fixed effect taxonomy
(ADR-0004), not a new decision invented here**: ``Effect``
(``domain/capability.py``) has exactly two non-``DENY``-by-default
options for anything leaving the machine at all --
``EGRESS_SENSITIVE`` (floors ``CONFIRM``) and ``EGRESS_SECRET`` (floors
``DENY``, ADR-0038). ``EGRESS_LOCAL`` floors ``ALLOW``, but its name
and its floor both say "stays on this machine" -- using it for a
genuine cloud-provider call would mislabel real internet egress as
local, which is a correctness bug, not a naming nitpick. There is no
third, ALLOW-tier "external egress, but definitely fine" effect in the
fixed taxonomy. So every cloud-provider call -- regardless of how
innocuous a specific task's data looks -- floors at ``CONFIRM`` at
minimum; only ``Classification.SECRET`` pushes it further, to the
unconditional ``DENY`` ADR-0038 established.
"""

from __future__ import annotations

from jarvis.domain.capability import Effect
from jarvis.domain.provenance import Classification


def egress_effect_for(classification: Classification) -> Effect:
    """Return the Effect a cloud-provider CapabilityInvocation must declare for ``classification``.

    Args:
        classification: The real classification of the task content
            being sent to a cloud provider.

    Returns:
        ``Effect.EGRESS_SECRET`` for ``Classification.SECRET`` (ADR-0038:
        an unconditional ``DENY``, no exception path). ``Effect.EGRESS_SENSITIVE``
        for everything else (``PUBLIC``, ``PERSONAL``, ``SENSITIVE``) --
        the fixed taxonomy's only other real-egress option, and the
        fail-closed choice (ADR-0016) when no ALLOW-tier external-egress
        effect exists to fall back to.
    """
    if classification is Classification.SECRET:
        return Effect.EGRESS_SECRET
    return Effect.EGRESS_SENSITIVE
