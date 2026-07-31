"""Orchestrates authorization decisions.

:class:`~jarvis.application.policy.orchestrator.AuthorizationOrchestrator`
is the one real entry point the rest of the system calls to authorize a
capability invocation: it constructs no decision logic of its own, it
calls the pure ``jarvis.domain.policy.evaluate()`` -- the actual
decision logic -- and then audit-logs whatever ``Decision`` comes back,
granted or denied, before returning it.

Gathering a real ``PolicyContext`` from ports (e.g. presence signals)
and acting further on a returned ``Decision`` (blocking, prompting) are
not yet implemented here -- those arrive in later work packages, once
the relevant ports exist. This package currently contains exactly the
evaluate-then-audit path and nothing else.
"""

from __future__ import annotations

from .orchestrator import AuthorizationOrchestrator

__all__ = [
    "AuthorizationOrchestrator",
]
