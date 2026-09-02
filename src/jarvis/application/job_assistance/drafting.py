"""The drafting authorizer: routes one job_assistance.draft invocation through the real choke point.

:class:`DraftWriteAuthorizer` mirrors
``jarvis.application.memory.writer.MemoryWriteAuthorizer`` exactly. A
fresh ``CapabilityDescriptor`` is built per call, with
:func:`~jarvis.application.job_assistance.classification.draft_effect_for`
resolving *this specific task's* real classification into the effect
that descriptor declares -- not a fixed effect registered once, the
same reason ``MemoryWriteAuthorizer`` does not use ``authorize_by_id()``
against a static registry entry either: the correct effect genuinely
varies per call, based on real, per-invocation content.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.application.job_assistance.classification import draft_effect_for
from jarvis.domain.capability import CapabilityDescriptor, CapabilityId, CapabilityInvocation

if TYPE_CHECKING:
    from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
    from jarvis.domain.policy import Decision, PolicyContext
    from jarvis.domain.provenance import Tainted

JOB_ASSISTANCE_DRAFT_CAPABILITY_ID = CapabilityId("job_assistance.draft")


class DraftWriteAuthorizer:
    """Authorizes one real job_assistance.draft invocation through the real AuthorizationOrchestrator."""  # noqa: E501

    def __init__(self, orchestrator: AuthorizationOrchestrator) -> None:
        """Store the orchestrator every drafting authorization is routed through.

        Args:
            orchestrator: Owned by the caller, matching every other
                real consumer of ``AuthorizationOrchestrator`` in this
                repo -- this class never constructs its own.
        """
        self._orchestrator = orchestrator

    def authorize_draft(self, task: Tainted[str], context: PolicyContext) -> Decision:
        """Authorize running a drafting task for ``task``.

        Constructs a real ``CapabilityInvocation`` and routes it
        through the injected ``AuthorizationOrchestrator`` -- context
        is an explicit parameter, not silently pulled internally,
        matching ``AuthorizationOrchestrator``'s own "caller composes
        context explicitly" convention.

        Args:
            task: The real drafting task description a caller wants
                to run, with its own real provenance --
                ``task.provenance.classification`` is what decides
                which ``Effect`` this call declares
                (``draft_effect_for``).
            context: Facts about the environment this decision is made
                in (confirmation channel availability).

        Returns:
            The real ``Decision`` -- ``granted`` is ``True`` only if
            this specific drafting task is authorized right now.
            Already durably appended to the injected ``AuditChain`` by
            the time this returns. Actually running the drafting task
            (calling ``UnverifiableTaskHandler``, saving the result via
            ``DraftStoragePort``) is the caller's own responsibility,
            only if ``granted`` -- this method never touches either.
        """
        effect = draft_effect_for(task.provenance.classification)
        descriptor = CapabilityDescriptor(
            id=JOB_ASSISTANCE_DRAFT_CAPABILITY_ID,
            effects=effect,
            description=(
                "Draft a document (e.g. a cover letter) via M2's reasoning layer, "
                "saved to a real file for the user to review -- never sent or "
                "submitted anywhere by this system itself (ADR-0058)."
            ),
        )
        invocation = CapabilityInvocation(descriptor, task.map(lambda content: {"task": content}))
        return self._orchestrator.authorize(invocation, context)
