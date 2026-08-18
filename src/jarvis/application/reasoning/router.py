"""The model router: authorizes one reasoning-provider call through the real choke point.

:class:`ModelRouter` is where ADR-0039 becomes load-bearing for real:
reasoning-provider calls are modeled as real ``CapabilityInvocation``
objects, authorized through the existing ``AuthorizationOrchestrator``
and hash-chain-audited through the existing ``AuditChain``. Every call
this class authorizes -- granted or denied -- gets a real, tamper-evident
audit record, the same as ``ping``, ``music.*``, or ``fs.read_file``.

**Deliberately not decided here**: which specific
:class:`~jarvis.domain.reasoning.ProviderProfile` services which
:class:`~jarvis.domain.evidence.EscalationRung`. Nothing in the
recovered material (``m2-reasoning-layer.md``) or any real ADR
specifies a rung-to-provider assignment policy, and inventing one here
would be new, unresolved architecture, not "classification-gated rung
availability" as this work package was actually scoped. What this
class answers instead -- rung-agnostic, and the real gating mechanism
underneath whatever assignment policy a dispatcher (WP-37, not yet
built) eventually adds -- is: *is this specific provider authorized to
be called right now, with this specific task's real, tainted content*.
A local provider is always available (no egress at all,
``Effect.EGRESS_LOCAL``, floors ``ALLOW``); a cloud provider's
availability is gated by the task's real
:class:`~jarvis.domain.provenance.Classification` via
``classification.egress_effect_for`` -- which is where "rung
availability" actually becomes classification-gated: a rung that would
try a cloud provider is only as available as that provider's real
authorization outcome.

**Also deliberately not done here**, per ADR-0039's own Consequences
section: registering reasoning capabilities in
``kernel/capabilities.py``'s ``build_default_registry()``. This class
calls :meth:`~jarvis.application.policy.orchestrator.AuthorizationOrchestrator.authorize`
directly with a freshly constructed ``CapabilityDescriptor`` per call
(a supported, documented usage -- that method's own docstring names
"callers with unusual invocation-assembly needs"), not
``authorize_by_id()`` against a persistent registry. ADR-0039 assigns
the registry wiring to "M2's dispatcher," which is WP-37, not this one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.application.reasoning.classification import egress_effect_for
from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
)

if TYPE_CHECKING:
    from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
    from jarvis.domain.policy import Decision, PolicyContext
    from jarvis.domain.provenance import Tainted
    from jarvis.domain.reasoning import ProviderProfile


class ModelRouter:
    """Authorizes one reasoning-provider call through the real AuthorizationOrchestrator."""

    def __init__(self, orchestrator: AuthorizationOrchestrator) -> None:
        """Store the orchestrator every provider-call authorization is routed through.

        Args:
            orchestrator: Owned by the caller, matching every other
                real consumer of ``AuthorizationOrchestrator`` in this
                repo -- this class never constructs its own.
        """
        self._orchestrator = orchestrator

    def authorize_provider_call(
        self, profile: ProviderProfile, task: Tainted[str], context: PolicyContext
    ) -> Decision:
        """Authorize calling ``profile`` with ``task``'s real, tainted content.

        Constructs a real ``CapabilityInvocation`` and routes it
        through the injected ``AuthorizationOrchestrator`` -- context
        is an explicit parameter, not silently pulled internally,
        matching ``AuthorizationOrchestrator``'s own "caller composes
        context explicitly" convention (see that class's docstring).

        Args:
            profile: The reasoning provider a caller wants to invoke.
            task: The task content this specific call would send,
                tagged with its real provenance -- ``task.provenance.classification``
                is what decides which ``Effect`` a cloud call declares
                (``classification.egress_effect_for``); irrelevant for
                a local provider, which never egresses at all.
            context: Facts about the environment this decision is made
                in (confirmation channel availability).

        Returns:
            The real ``Decision`` -- ``granted`` is ``True`` only if
            this specific call is authorized right now. Already
            durably appended to the injected ``AuditChain`` by the
            time this returns (``AuthorizationOrchestrator.authorize``'s
            own guarantee).
        """
        effects = (
            Effect.EGRESS_LOCAL
            if profile.is_local
            else egress_effect_for(task.provenance.classification)
        )
        descriptor = CapabilityDescriptor(
            id=CapabilityId(f"reasoning.{profile.name}"),
            effects=effects,
            description=f"Send task content to reasoning provider {profile.name!r}.",
        )
        invocation = CapabilityInvocation(descriptor, task.map(lambda content: {"task": content}))
        return self._orchestrator.authorize(invocation, context)
