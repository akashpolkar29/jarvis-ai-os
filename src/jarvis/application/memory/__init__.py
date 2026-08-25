"""M4 memory-write authorization: the real ADR-0049 choke point.

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
"""

from __future__ import annotations

from .classification import memory_effect_for
from .writer import MEMORY_WRITE_CAPABILITY_ID, MemoryWriteAuthorizer

__all__ = [
    "MEMORY_WRITE_CAPABILITY_ID",
    "MemoryWriteAuthorizer",
    "memory_effect_for",
]
