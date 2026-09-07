"""The application-folder-preparation authorizer: routes one call through the real choke point.

:class:`PrepareApplicationFolderAuthorizer` mirrors
``jarvis.application.job_assistance.drafting.DraftWriteAuthorizer``
exactly -- a fresh ``CapabilityDescriptor`` is built per call, with
:func:`~jarvis.application.job_assistance.classification.prepare_application_folder_effect_for`
resolving *this specific call's* real effect (whether ``force`` was
given) into the descriptor it declares -- not a fixed effect
registered once, the same reason ``DraftWriteAuthorizer``/
``MemoryWriteAuthorizer`` do not use ``authorize_by_id()`` against a
static registry entry either.

This is a genuinely separate, outer authorization from
``job_assistance.draft``'s own (already-existing, unmodified) gate --
mirroring ``kernel/coding.py``'s own "an outer gate authorizes
invoking the whole operation; an inner, already-existing capability's
own gate separately authorizes its own sub-step" shape. Creating real
folders and copying real template files is this capability's own real
action, structurally distinct from generating the cover-letter body
text (which reuses ``authorize_and_draft_document`` completely
unmodified, its own dynamic-effect gate untouched).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.application.job_assistance.classification import (
    prepare_application_folder_effect_for,
)
from jarvis.domain.capability import CapabilityDescriptor, CapabilityId, CapabilityInvocation

if TYPE_CHECKING:
    from collections.abc import Mapping

    from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
    from jarvis.domain.policy import Decision, PolicyContext
    from jarvis.domain.provenance import Tainted

JOB_ASSISTANCE_PREPARE_APPLICATION_FOLDER_CAPABILITY_ID = CapabilityId(
    "job_assistance.prepare_application_folder"
)


class PrepareApplicationFolderAuthorizer:
    """Authorizes one real prepare-application-folder invocation through the real orchestrator."""

    def __init__(self, orchestrator: AuthorizationOrchestrator) -> None:
        """Store the orchestrator every such authorization is routed through.

        Args:
            orchestrator: Owned by the caller, matching every other
                real consumer of ``AuthorizationOrchestrator`` in this
                repo -- this class never constructs its own.
        """
        self._orchestrator = orchestrator

    def authorize_prepare(
        self,
        arguments: Tainted[Mapping[str, object]],
        *,
        force: bool,
        context: PolicyContext,
    ) -> Decision:
        """Authorize creating/copying one real application folder's own content.

        Args:
            arguments: The call's real, already-provenanced arguments
                (month label, template paths, job title, company) --
                kept opaque here (a plain mapping) since this
                authorizer's only real job is to resolve the correct
                ``Effect``, not to interpret the arguments' own
                meaning.
            force: Whether the caller explicitly requested overwriting
                a real, existing application folder's own content --
                see :func:`~jarvis.application.job_assistance.classification.prepare_application_folder_effect_for`.
            context: Facts about the environment this decision is made
                in (confirmation channel availability).

        Returns:
            The real ``Decision`` -- ``granted`` is ``True`` only if
            this specific call is authorized right now. Already
            durably appended to the injected ``AuditChain`` by the
            time this returns. Actually creating the real folders,
            copying the real template files, and (separately)
            authorizing/running the cover-letter body drafting are the
            caller's own responsibility, only if ``granted``.
        """  # noqa: E501
        effect = prepare_application_folder_effect_for(force=force)
        descriptor = CapabilityDescriptor(
            id=JOB_ASSISTANCE_PREPARE_APPLICATION_FOLDER_CAPABILITY_ID,
            effects=effect,
            description=(
                "Create a real, local application folder (CV/ and Cover Letter/ "
                "subfolders) from the user's own real template files, for a "
                "specific job application. Never reads Overleaf, never submits "
                "or applies anywhere itself (ADR-0058)."
            ),
        )
        invocation = CapabilityInvocation(descriptor, arguments)
        return self._orchestrator.authorize(invocation, context)
