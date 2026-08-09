"""Orchestrates authorization decisions.

:class:`~jarvis.application.policy.orchestrator.AuthorizationOrchestrator`
is the one real entry point the rest of the system calls to authorize a
capability invocation, either directly (``authorize()``, given an
already-built ``CapabilityInvocation``) or by id (``authorize_by_id()``,
which looks the descriptor up in an injected
``jarvis.domain.registry.CapabilityRegistry`` first). Either way, it
constructs no decision logic of its own: it calls the pure
``jarvis.domain.policy.evaluate()`` -- the actual decision logic -- and
then audit-logs whatever ``Decision`` comes back, granted or denied,
before returning it.

It also exposes read-only introspection over that same registry --
``is_registered()`` and ``list_capabilities()`` -- for callers (a
future kernel/CLI) that need to answer "what can I even call" without
that question itself being an authorization decision: neither touches
``evaluate()`` or the audit chain.

Gathering a real ``PolicyContext`` from ports (e.g. presence signals)
and acting further on a returned ``Decision`` (blocking, prompting) are
not yet implemented here -- those arrive in later work packages, once
the relevant ports exist. This package currently contains exactly the
lookup/evaluate-then-audit path plus registry introspection, and
nothing else.
"""

from __future__ import annotations

from .orchestrator import AuthorizationOrchestrator

__all__ = [
    "AuthorizationOrchestrator",
]
