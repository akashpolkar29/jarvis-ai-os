"""Orchestrates the M2 escalation ladder: which rung to try next, and when to stop.

:class:`~jarvis.application.reasoning.ladder.EscalationLadder` is the
one real entry point for deciding what a dispatcher (WP-37, not yet
built) should try next for a task, given every :class:`~jarvis.domain.evidence.Attempt`
made so far. It decides nothing about *how* a rung is executed (that's
``jarvis.ports.reasoning``/``jarvis.ports.validation``) or *whether*
there is budget left to try it (that's
:class:`~jarvis.domain.reasoning.TaskBudget`, enforced at the
dispatcher per deliverable #6, not by the ladder itself) -- only
*which rung comes next*, or that escalation should stop.
"""

from __future__ import annotations

from .ladder import EscalationLadder

__all__ = [
    "EscalationLadder",
]
