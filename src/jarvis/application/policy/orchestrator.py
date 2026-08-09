"""The authorization orchestrator: the one real entry point for authorizing a call.

:class:`AuthorizationOrchestrator` wires the pure domain pieces
together into the actual callable path the rest of the system uses.
It offers two ways in:

* :meth:`authorize` -- takes an already-built
  :class:`~jarvis.domain.capability.CapabilityInvocation` directly,
  for callers that already have one (tests, or callers with unusual
  invocation-assembly needs).
* :meth:`authorize_by_id` -- takes a
  :class:`~jarvis.domain.capability.CapabilityId` and the call's
  :class:`~jarvis.domain.provenance.Tainted` arguments, looks the
  descriptor up in the injected
  :class:`~jarvis.domain.registry.CapabilityRegistry`, builds the
  invocation, and delegates to :meth:`authorize`. Looking a descriptor
  up by id is pure plumbing, not a taint decision -- the caller still
  supplies the arguments' real provenance directly, exactly as with
  :meth:`authorize`, so this does not change who decides whether an
  argument is trusted.

Both paths converge on the same evaluate-then-audit logic:
:func:`~jarvis.domain.policy.evaluate` produces a
:class:`~jarvis.domain.policy.Decision`, and that decision is appended
to an injected :class:`~jarvis.domain.audit.AuditChain` -- every
decision, granted or denied, with no exceptions.

Unlike ``evaluate()``, this class is deliberately stateful: it owns no
data of its own beyond references to the chain and registry it was
given, but that reference is exactly why this logic lives here and
not in ``domain``. Both the chain and the registry are constructor-
injected, never constructed internally, so their lifetimes are the
caller's to manage (share either across orchestrators, reload either
from storage, etc).

Ordering guarantee: the audit append happens strictly before
``authorize()`` returns, and any failure from the append (e.g.
:class:`~jarvis.domain.errors.AuditRecordNotSerializable`) is left to
propagate uncaught. This makes it structurally impossible to observe
a ``Decision`` -- granted or denied -- that was not already durably
appended to the chain: either both the append and the return happen,
or neither does. The same is true, one step earlier, of
``authorize_by_id()``'s registry lookup: a
:class:`~jarvis.domain.errors.CapabilityNotRegistered` failure happens
before ``evaluate()`` is ever called, so nothing is computed and
nothing is appended either way.

Two further methods, :meth:`is_registered` and :meth:`list_capabilities`,
give read-only introspection into the injected registry -- "is this
callable" and "what's callable at all", for a future kernel/CLI to
answer "what can I even call". Neither is a decision: neither calls
``evaluate()`` nor touches the audit chain. They exist alongside the
authorize paths only because the orchestrator is already the one
thing holding the registry reference.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.domain.capability import CapabilityInvocation
from jarvis.domain.policy import evaluate

if TYPE_CHECKING:
    from collections.abc import Mapping

    from jarvis.domain.audit import AuditChain
    from jarvis.domain.capability import CapabilityDescriptor, CapabilityId
    from jarvis.domain.policy import Decision, PolicyContext
    from jarvis.domain.provenance import Tainted
    from jarvis.domain.registry import CapabilityRegistry


class AuthorizationOrchestrator:
    """Evaluates and audit-logs every capability invocation it authorizes."""

    def __init__(self, chain: AuditChain, registry: CapabilityRegistry) -> None:
        """Store the audit chain and capability registry this orchestrator uses.

        Args:
            chain: The chain to append decisions to. Owned by the
                caller -- this class never constructs its own, so a
                chain can be shared across orchestrator instances or
                reloaded from storage by the caller.
            registry: The registry to look capability descriptors up
                in for :meth:`authorize_by_id`. Owned by the caller,
                for the same reason as ``chain``.
        """
        self._chain = chain
        self._registry = registry

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

    def authorize_by_id(
        self,
        capability_id: CapabilityId,
        arguments: Tainted[Mapping[str, object]],
        context: PolicyContext,
    ) -> Decision:
        """Look ``capability_id`` up in the registry, then authorize it like :meth:`authorize`.

        Args:
            capability_id: The id of the capability to invoke.
            arguments: The call's arguments, tagged with their real
                provenance -- the same as would be passed to
                :meth:`authorize` inside a ``CapabilityInvocation``.
                Looking a descriptor up by id does not change who
                decides an argument's provenance; that remains the
                caller's responsibility here exactly as it does there.
            context: Facts about the environment the decision is made in.

        Returns:
            The same as :meth:`authorize`, for the invocation built
            from the looked-up descriptor and ``arguments``.

        Raises:
            jarvis.domain.errors.CapabilityNotRegistered: If no
                descriptor is registered under ``capability_id``.
                Propagated unchanged from the registry -- it already
                says exactly what went wrong, and this happens before
                ``evaluate()`` is ever called, so nothing is computed
                and nothing is appended to the chain.
            jarvis.domain.errors.AuditRecordNotSerializable: As in
                :meth:`authorize`.
        """
        descriptor = self._registry.get(capability_id)
        invocation = CapabilityInvocation(descriptor, arguments)
        return self.authorize(invocation, context)

    def is_registered(self, capability_id: CapabilityId) -> bool:
        """Return whether a descriptor is registered under ``capability_id``.

        Not a decision -- this does not call ``evaluate()`` and is not
        audit-logged, exactly like :meth:`list_capabilities`.

        Args:
            capability_id: The id to check.

        Returns:
            ``True`` if a descriptor is registered under ``capability_id``,
            ``False`` otherwise.
        """
        return capability_id in self._registry

    def list_capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        """Return every descriptor currently registered.

        Not a decision -- this does not call ``evaluate()`` and is not
        audit-logged, exactly like :meth:`is_registered`.

        Returns:
            A snapshot tuple of every registered descriptor. Order is
            not part of this method's contract, matching
            :class:`~jarvis.domain.registry.CapabilityRegistry`'s own
            iteration-order disclaimer.
        """
        return tuple(self._registry)
