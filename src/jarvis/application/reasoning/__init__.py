"""Orchestrates the M2 escalation ladder: which rung to try next, when to stop, and who wins.

:class:`~jarvis.application.reasoning.ladder.EscalationLadder` is the
one real entry point for deciding what a dispatcher (WP-37, not yet
built) should try next for a task, given every :class:`~jarvis.domain.evidence.Attempt`
made so far. It decides nothing about *how* a rung is executed (that's
``jarvis.ports.reasoning``/``jarvis.ports.validation``) or *whether*
there is budget left to try it (that's
:class:`~jarvis.domain.reasoning.TaskBudget`, enforced at the
dispatcher per deliverable #6, not by the ladder itself) -- only
*which rung comes next*, or that escalation should stop.

:class:`~jarvis.application.reasoning.arbiter.Arbiter` decides who wins
when more than one competing attempt exists: it selects exactly one
``Candidate``, unmodified (ADR-0023), scored by real validation
evidence with self-authored evidence excluded (ADR-0025).

:class:`~jarvis.application.reasoning.router.ModelRouter` authorizes
one reasoning-provider call through the real
``AuthorizationOrchestrator``/``AuditChain`` choke point (ADR-0039),
using :func:`~jarvis.application.reasoning.classification.egress_effect_for`
to decide which ``Effect`` a cloud-provider call declares for a given
task's real Classification.
"""

from __future__ import annotations

from .arbiter import Arbiter
from .classification import egress_effect_for
from .ladder import EscalationLadder
from .router import ModelRouter

__all__ = [
    "Arbiter",
    "EscalationLadder",
    "ModelRouter",
    "egress_effect_for",
]
