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

**No real caller yet, deliberately** -- this package's own real
integration with a coding-loop wrapper (ADR-0055) is WP-71, explicitly
out of the work package that built this one's own scope. See
``tests/meta/test_workspace_apply_patch_single_path.py``'s own
docstring for the real, still-open question that work will need to
resolve.
"""

from __future__ import annotations

from .classification import (
    UnrecognizedTestConventionError,
    code_write_effect_for,
    detect_protected_patterns,
    resolve_protected_patterns,
)
from .writer import CODE_WRITE_CAPABILITY_ID, CodeWriteAuthorizer

__all__ = [
    "CODE_WRITE_CAPABILITY_ID",
    "CodeWriteAuthorizer",
    "UnrecognizedTestConventionError",
    "code_write_effect_for",
    "detect_protected_patterns",
    "resolve_protected_patterns",
]
