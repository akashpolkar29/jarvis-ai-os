"""The authorization orchestrator: the one real entry point for authorizing a call.

:class:`AuthorizationOrchestrator` wires the pure domain pieces together
into the actual callable path the rest of the system uses: it takes a
:class:`~jarvis.domain.capability.CapabilityInvocation` and a
:class:`~jarvis.domain.policy.PolicyContext`, asks
:func:`~jarvis.domain.policy.evaluate` for a
:class:`~jarvis.domain.policy.Decision`, and appends that decision to
an injected :class:`~jarvis.domain.audit.AuditChain` -- every decision,
granted or denied, with no exceptions.

Unlike ``evaluate()``, this class is deliberately stateful: it owns no
data of its own beyond a reference to the chain it was given, but that
reference is exactly why this logic lives here and not in ``domain``.
The chain is constructor-injected, never constructed internally, so
its lifetime is the caller's to manage (share one chain across
orchestrators, reload one from storage, etc).

Ordering guarantee: the audit append happens strictly before
``authorize()`` returns, and any failure from the append (e.g.
:class:`~jarvis.domain.errors.AuditRecordNotSerializable`) is left to
propagate uncaught. This makes it structurally impossible to observe a
``Decision`` -- granted or denied -- that was not already durably
appended to the chain: either both the append and the return happen,
or neither does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.domain.policy import evaluate

if TYPE_CHECKING:
    from jarvis.domain.audit import AuditChain
    from jarvis.domain.capability import CapabilityInvocation
    from jarvis.domain.policy import Decision, PolicyContext


class AuthorizationOrchestrator:
    """Evaluates and audit-logs every capability invocation it authorizes."""

    def __init__(self, chain: AuditChain) -> None:
        """Store the audit chain this orchestrator appends every decision to.

        Args:
            chain: The chain to append decisions to. Owned by the
                caller -- this class never constructs its own, so a
                chain can be shared across orchestrator instances or
                reloaded from storage by the caller.
        """
        self._chain = chain

    def authorize(self, invocation: CapabilityInvocation, context: PolicyContext) -> Decision:
        """Evaluate ``invocation`` under ``context`` and audit-log the outcome.

        Args:
            invocation: The capability invocation to authorize.
            context: Facts about the environment the decision is made in.

        Returns:
            The ``Decision`` produced by ``evaluate()`` -- guaranteed to
            already be appended to the injected chain by the time this
            returns.

        Raises:
            jarvis.domain.errors.AuditRecordNotSerializable: If the
                decision's content cannot be appended to the chain. Not
                caught here: a decision that cannot be audited must not
                be handed back to the caller as though it were granted
                or denied.
        """
        decision = evaluate(invocation, context)
        self._chain.append(decision)
        return decision
