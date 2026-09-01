"""M5 coding-agent write authorization: the real ADR-0056 choke point.

:func:`~jarvis.application.coding.classification.code_write_effect_for`
maps a real target path to the :class:`~jarvis.domain.capability.Effect`
a coding-agent write ``CapabilityInvocation`` must declare --
``Effect.PROTECTED_PATH_WRITE`` (floors ``Tier.DENY``, unconditional)
for a path matching a real, resolved protected-path pattern,
``Effect.CODE_WRITE`` (floors ``Tier.CONFIRM``) for everything else.

:func:`~jarvis.application.coding.classification.resolve_protected_patterns`
is ADR-0056's own amendment: a real, fail-closed resolution of which
patterns actually apply to a given target repository --
:func:`~jarvis.application.coding.classification.detect_protected_patterns`
first, an explicit, caller-supplied override always taking precedence,
and a real :class:`~jarvis.application.coding.classification.UnrecognizedTestConventionError`
raised rather than silently defaulting to patterns that were never
confirmed to match.

:class:`~jarvis.application.coding.writer.CodeWriteAuthorizer` authorizes
one real coding-agent write through the existing
``AuthorizationOrchestrator``/``AuditChain`` choke point, mirroring
``jarvis.application.memory.writer.MemoryWriteAuthorizer`` exactly.

:func:`~jarvis.application.coding.sandbox_workspace.make_disposable_workspace`
is WP-73, ADR-0055's own "Amendment 2026-09-01" fix: ``Dispatcher.run()``
was confirmed to call ``WorkspacePort.apply_patch`` internally, once
per candidate at every rung, with no seam a wrapper could intercept
before that write happens. This function gives ``Dispatcher.run()`` a
real, disposable, ``SandboxPort``-made copy of a target repository
instead of the real one, so those internal writes can only ever touch
the copy.

:func:`~jarvis.application.coding.patch_paths.touched_paths` is ADR-0056's
own amendment 2: parses which real, canonicalized paths a patch touches
from its own unified-diff headers, treating a created file identically
to a modified one, and surfacing a repository-escaping path (a real
``../``-style or symlink escape) as an absolute result callers must
reject outright rather than pattern-match.

:func:`~jarvis.application.coding.loop.run_coding_task` is WP-71, the
real coding-loop wrapper ADR-0055 (as amended) describes: every
``Dispatcher.run()`` climb runs against a fresh WP-73 disposable
workspace; a real, finite retry budget bounds how many climbs are
attempted; once a winning candidate reaches ``Verdict.PASSED``, every
path it touches is authorized individually and, only if every single
one is granted, exactly one real write happens against the actual
target repository -- otherwise no write happens at all.

**No real caller yet, deliberately** -- this package's own real
integration with a kernel composition root (``kernel/coding.py``,
WP-72) is explicitly out of this work package's own scope.
"""

from __future__ import annotations

from .classification import (
    UnrecognizedTestConventionError,
    code_write_effect_for,
    detect_protected_patterns,
    resolve_protected_patterns,
)
from .loop import (
    CodingLoopDependencies,
    CodingLoopOutcome,
    CodingLoopResult,
    CodingTaskRequest,
    run_coding_task,
)
from .patch_paths import touched_paths
from .sandbox_workspace import (
    DisposableWorkspace,
    DisposableWorkspaceCopyFailedError,
    make_disposable_workspace,
)
from .writer import CODE_WRITE_CAPABILITY_ID, CodeWriteAuthorizer

__all__ = [
    "CODE_WRITE_CAPABILITY_ID",
    "CodeWriteAuthorizer",
    "CodingLoopDependencies",
    "CodingLoopOutcome",
    "CodingLoopResult",
    "CodingTaskRequest",
    "DisposableWorkspace",
    "DisposableWorkspaceCopyFailedError",
    "UnrecognizedTestConventionError",
    "code_write_effect_for",
    "detect_protected_patterns",
    "make_disposable_workspace",
    "resolve_protected_patterns",
    "run_coding_task",
    "touched_paths",
]
