"""M4 memory write/retrieval authorization: the real ADR-0049/ADR-0050 choke points.

:func:`~jarvis.application.memory.classification.memory_effect_for`
maps a to-be-memorized value's real
:class:`~jarvis.domain.provenance.Classification` to the
:class:`~jarvis.domain.capability.Effect` a memory-write
``CapabilityInvocation`` must declare -- ``Effect.MEMORY_WRITE``
(floors ``Tier.DENY``, unconditional) for ``Classification.SECRET``
only, ``Effect.WRITE_LOCAL`` (floors ``Tier.CONFIRM``, unchanged) for
everything else.

:class:`~jarvis.application.memory.writer.MemoryWriteAuthorizer`
authorizes one real memory-write invocation through the existing
``AuthorizationOrchestrator``/``AuditChain`` choke point, mirroring
``jarvis.application.reasoning.router.ModelRouter`` exactly: a fresh
``CapabilityDescriptor`` is built per call, with the effect resolved
dynamically from the *value's own* real classification, not a fixed
effect registered once -- the same reason ``ModelRouter`` does not use
``authorize_by_id()`` against a static registry entry.

:func:`~jarvis.application.memory.retrieval_guard.exclude_secret_records`
is ADR-0050's own amendment: an unconditional, adapter-independent
exclusion of any ``Classification.SECRET`` record from a query's
results, redundant with the write-time guarantee above on purpose.
"""

from __future__ import annotations

from .classification import memory_effect_for
from .retrieval_guard import exclude_secret_records
from .writer import MEMORY_WRITE_CAPABILITY_ID, MemoryWriteAuthorizer

__all__ = [
    "MEMORY_WRITE_CAPABILITY_ID",
    "MemoryWriteAuthorizer",
    "exclude_secret_records",
    "memory_effect_for",
]
