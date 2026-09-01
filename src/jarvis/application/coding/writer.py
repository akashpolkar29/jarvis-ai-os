"""The code-write authorizer: routes one coding-agent write through the real choke point.

:class:`CodeWriteAuthorizer` is where ADR-0056 becomes load-bearing for
real -- mirroring
:class:`~jarvis.application.memory.writer.MemoryWriteAuthorizer`
exactly. A fresh ``CapabilityDescriptor`` is built per call, with
:func:`~jarvis.application.coding.classification.code_write_effect_for`
resolving *this specific write's own target path* into the effect that
descriptor declares -- not a fixed effect registered once, the same
reason ``MemoryWriteAuthorizer`` does not use ``authorize_by_id()``
against a static registry entry: the correct effect genuinely varies
per invocation, based on real, per-invocation content (here, which
path is being written), not something fixable at registration time.

**No real caller yet, deliberately** -- WP-71 (the coding-loop wrapper
itself, ADR-0055) is explicitly out of this work package's own scope.
This class is real and independently tested (mirroring how
``MemoryWriteAuthorizer`` itself predates ``kernel/memory.py``'s own
composition root by several work packages), not wired into anything
that calls ``WorkspacePort.apply_patch`` yet -- see
``tests/meta/test_workspace_apply_patch_single_path.py``'s own
docstring for the real, still-open question of how a future caller
integrates this authorizer with M2's own ``Dispatcher``-internal
patch-application flow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.application.coding.classification import code_write_effect_for
from jarvis.domain.capability import CapabilityDescriptor, CapabilityId, CapabilityInvocation
from jarvis.domain.provenance import Provenance, Tainted

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
    from jarvis.domain.policy import Decision, PolicyContext

CODE_WRITE_CAPABILITY_ID = CapabilityId("coding.write")


class CodeWriteAuthorizer:
    """Authorizes one real coding-agent file-write invocation through the real orchestrator."""

    def __init__(self, orchestrator: AuthorizationOrchestrator) -> None:
        """Store the orchestrator every coding-agent write authorization is routed through.

        Args:
            orchestrator: Owned by the caller, matching every other
                real consumer of ``AuthorizationOrchestrator`` in this
                repo -- this class never constructs its own.
        """
        self._orchestrator = orchestrator

    def authorize_write(
        self, path: Path, protected_patterns: tuple[str, ...], context: PolicyContext
    ) -> Decision:
        """Authorize writing to ``path``.

        Args:
            path: The real target path a coding-agent patch wants to
                write, relative to the target repository's own root
                (see ``code_write_effect_for``'s own docstring for why
                this precondition matters -- this method inherits it
                unchanged, it does not itself resolve or canonicalize
                ``path``).
            protected_patterns: The real, already-resolved patterns to
                check ``path`` against (``resolve_protected_patterns``'s
                own real, fail-closed output) -- this class does not
                itself resolve them, matching every other authorizer in
                this repo's own "caller composes context explicitly"
                convention.
            context: Facts about the environment this decision is made
                in (confirmation channel availability).

        Returns:
            The real ``Decision`` -- ``granted`` is ``True`` only if
            this specific write is authorized right now. Already
            durably appended to the injected ``AuditChain`` by the
            time this returns. The real write itself
            (``WorkspacePort.apply_patch``) is the caller's own
            responsibility, only if ``granted`` -- this method never
            touches a workspace.
        """
        effect = code_write_effect_for(path, protected_patterns)
        descriptor = CapabilityDescriptor(
            id=CODE_WRITE_CAPABILITY_ID,
            effects=effect,
            description="Write to a file on behalf of a coding-agent task.",
        )
        invocation = CapabilityInvocation(
            descriptor, Tainted({"path": str(path)}, Provenance.user())
        )
        return self._orchestrator.authorize(invocation, context)
