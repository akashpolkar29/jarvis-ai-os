"""The memory-write authorizer: routes one memory-write invocation through the real choke point.

:class:`MemoryWriteAuthorizer` is where ADR-0049 becomes load-bearing
for real -- mirroring
``jarvis.application.reasoning.router.ModelRouter`` exactly. A fresh
``CapabilityDescriptor`` is built per call, with
:func:`~jarvis.application.memory.classification.memory_effect_for`
resolving *this specific value's* real classification into the effect
that descriptor declares -- not a fixed effect registered once, the
same reason ``ModelRouter`` does not use ``authorize_by_id()`` against
a static registry entry: the correct effect genuinely varies per call,
based on real, per-invocation content, not something fixable at
registration time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.application.memory.classification import memory_effect_for
from jarvis.domain.capability import CapabilityDescriptor, CapabilityId, CapabilityInvocation

if TYPE_CHECKING:
    from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
    from jarvis.domain.policy import Decision, PolicyContext
    from jarvis.domain.provenance import Tainted

MEMORY_WRITE_CAPABILITY_ID = CapabilityId("memory.write")
MEMORY_UPDATE_CAPABILITY_ID = CapabilityId("memory.update")
"""A distinct id from memory.write (WP-107), not folded into it: the audit
chain should be able to tell "a new record was created" apart from "an
existing one was mutated in place" when read back later, the same
reason pin/forget each got their own id rather than reusing write's."""


class MemoryWriteAuthorizer:
    """Authorizes one real memory-write invocation through the real AuthorizationOrchestrator."""

    def __init__(self, orchestrator: AuthorizationOrchestrator) -> None:
        """Store the orchestrator every memory-write authorization is routed through.

        Args:
            orchestrator: Owned by the caller, matching every other
                real consumer of ``AuthorizationOrchestrator`` in this
                repo -- this class never constructs its own.
        """
        self._orchestrator = orchestrator

    def authorize_write[T](self, value: Tainted[T], context: PolicyContext) -> Decision:
        """Authorize writing ``value`` to memory.

        Constructs a real ``CapabilityInvocation`` and routes it
        through the injected ``AuthorizationOrchestrator`` -- context
        is an explicit parameter, not silently pulled internally,
        matching ``AuthorizationOrchestrator``'s own "caller composes
        context explicitly" convention.

        Args:
            value: The value a caller wants to write to memory, with
                its own real provenance -- ``value.provenance.classification``
                is what decides which ``Effect`` this call declares
                (``memory_effect_for``).
            context: Facts about the environment this decision is made
                in (confirmation channel availability).

        Returns:
            The real ``Decision`` -- ``granted`` is ``True`` only if
            this specific write is authorized right now. Already
            durably appended to the injected ``AuditChain`` by the
            time this returns (``AuthorizationOrchestrator.authorize``'s
            own guarantee). The real write to ``MemoryWritePort``
            itself is the caller's own responsibility, only if
            ``granted`` -- this method never touches the port.
        """
        effect = memory_effect_for(value.provenance.classification)
        descriptor = CapabilityDescriptor(
            id=MEMORY_WRITE_CAPABILITY_ID,
            effects=effect,
            description="Write a value to memory.",
        )
        invocation = CapabilityInvocation(descriptor, value.map(lambda content: {"value": content}))
        return self._orchestrator.authorize(invocation, context)

    def authorize_update[T](
        self, identifier: str, value: Tainted[T], context: PolicyContext
    ) -> Decision:
        """Authorize updating the record at ``identifier`` to ``value`` (WP-107).

        Mirrors :meth:`authorize_write` exactly -- the correct
        ``Effect`` is resolved from the *new* value's own real
        classification, the identical reasoning ADR-0049 already
        applies to a fresh write: updating an existing record to
        SECRET content is exactly as real a risk as creating one with
        SECRET content in the first place, and must floor identically.

        Args:
            identifier: The real, existing record's identifier being
                updated -- carried in the invocation only for the
                audit trail; it is not itself classifiable content.
            value: The new value a caller wants to store at
                ``identifier``, with its own real provenance.
            context: Facts about the environment this decision is made
                in.

        Returns:
            The real ``Decision`` -- already durably appended to the
            injected ``AuditChain``. The real update to
            ``MemoryWritePort`` itself is the caller's own
            responsibility, only if ``granted``.
        """
        effect = memory_effect_for(value.provenance.classification)
        descriptor = CapabilityDescriptor(
            id=MEMORY_UPDATE_CAPABILITY_ID,
            effects=effect,
            description="Update an existing memory record's value.",
        )
        invocation = CapabilityInvocation(
            descriptor, value.map(lambda content: {"identifier": identifier, "value": content})
        )
        return self._orchestrator.authorize(invocation, context)
