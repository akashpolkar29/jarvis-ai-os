"""Classification -> Effect mapping for M4 memory-write capability invocations.

Kept separate from ``writer.py`` deliberately, mirroring
``jarvis.application.reasoning.classification``'s own split exactly:
this is the one pure decision ("given this value's real Classification,
which ``Effect`` must a memory-write call declare") that
:class:`~jarvis.application.memory.writer.MemoryWriteAuthorizer`
orchestrates around.

**A new effect, not a reuse of an existing one -- ADR-0049's own
reasoning, restated here at the point it matters**: ``Effect.EGRESS_SECRET``
(ADR-0038) already floors ``Tier.DENY`` for ``Classification.SECRET``,
but its own name and reasoning are specifically about a value *leaving
this machine* to a cloud provider. A memory write never leaves the
machine at all -- reusing that name here would make the effect
taxonomy actively misleading. ``Effect.MEMORY_WRITE`` is the real,
separate effect ADR-0049 introduces instead, floors ``Tier.DENY`` the
same unconditional way.
"""

from __future__ import annotations

from jarvis.domain.capability import Effect
from jarvis.domain.provenance import Classification


def memory_effect_for(classification: Classification) -> Effect:
    """Return the Effect a memory-write CapabilityInvocation must declare for ``classification``.

    Args:
        classification: The real classification of the value being
            written to memory.

    Returns:
        ``Effect.MEMORY_WRITE`` for ``Classification.SECRET`` (ADR-0049:
        an unconditional ``DENY``, no exception path -- memory is a
        real persistence/exfiltration surface, treated with the same
        zero-tolerance this project already applies to cloud egress).
        ``Effect.WRITE_LOCAL`` for everything else (``PUBLIC``,
        ``PERSONAL``, ``SENSITIVE``) -- the ordinary local-write floor
        (``Tier.CONFIRM``), unchanged and not specially restricted
        beyond that by ADR-0049.
    """
    if classification is Classification.SECRET:
        return Effect.MEMORY_WRITE
    return Effect.WRITE_LOCAL
