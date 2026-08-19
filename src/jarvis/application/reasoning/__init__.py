"""Orchestrates the M2 escalation ladder: which rung to try next, when to stop, and who wins.

:class:`~jarvis.application.reasoning.ladder.EscalationLadder` is the
one real entry point for deciding what
:class:`~jarvis.application.reasoning.dispatcher.Dispatcher` should
try next for a task, given every :class:`~jarvis.domain.evidence.Attempt`
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

:class:`~jarvis.application.reasoning.dispatcher.Dispatcher` wires all
three together, end-to-end, with real ``TaskBudget`` enforcement --
see that module's own docstring for what it decided about a budget
unit's meaning and the real, flagged ``DETERMINISTIC_FIX`` gap.

:class:`~jarvis.application.reasoning.outcome_logger.OutcomeLogger`
records non-authoritative engineering telemetry only (which rung, how
long, pass/fail) -- see that module's own docstring for how ADR-0039's
"must never become a second, unaudited authorization record" is
structurally enforced, not just documented.

:class:`~jarvis.application.reasoning.unverifiable.UnverifiableTaskHandler`
is deliverable #7's unverifiable-task regime: parallel heterogeneous
generation with escalation structurally off (no ladder, no arbiter --
see that module's own docstring), a human picking the winner via
:class:`~jarvis.ports.candidate_presentation.CandidatePresentationPort`
instead of evidence-based scoring.
"""

from __future__ import annotations

from .arbiter import Arbiter
from .classification import egress_effect_for
from .dispatcher import Dispatcher, DispatchResult
from .ladder import EscalationLadder
from .outcome_logger import Outcome, OutcomeLogger
from .router import ModelRouter
from .unverifiable import NoProviderAuthorizedError, UnverifiableTaskHandler

__all__ = [
    "Arbiter",
    "DispatchResult",
    "Dispatcher",
    "EscalationLadder",
    "ModelRouter",
    "NoProviderAuthorizedError",
    "Outcome",
    "OutcomeLogger",
    "UnverifiableTaskHandler",
    "egress_effect_for",
]
