"""Classification -> Effect mapping for M6b's job-assistance drafting capability.

Kept separate from ``drafting.py`` deliberately, mirroring
``jarvis.application.memory.classification``'s own split from
``jarvis.application.memory.writer`` exactly: this is the one pure
decision ("given this drafting task's real Classification, which
``Effect`` must a ``job_assistance.draft`` invocation declare") that
:class:`~jarvis.application.job_assistance.drafting.DraftWriteAuthorizer`
orchestrates around.

**A real, conservative implementation default -- not a decision --
flagged for the user's own confirmation.**
`docs/architecture/m6b-job-assistance.md`'s own design left this
question genuinely open: whether ``Classification.SECRET`` drafting
input deserves the same unconditional-DENY, never-persisted
protection ``Effect.MEMORY_WRITE`` (ADR-0049) already gives memory
writes, or the ordinary ``Effect.WRITE_LOCAL``/``Tier.CONFIRM`` floor
the design doc's own static-capability sketch first assumed.
Implementing this function forces a concrete choice regardless -- some
real behavior must exist the first time real ``SECRET`` content is
passed as drafting input, static-vs-dynamic is not itself an
avoidable question once real code exists. **The conservative choice
made here: ``SECRET`` reuses ``Effect.MEMORY_WRITE``'s own
unconditional ``DENY`` floor**, deliberately reusing that existing
enum member's real tier-floor *behavior* rather than minting a new,
permanent one -- not a claim that a drafted document conceptually *is*
a memory write, but the smallest, most reversible way to get
DENY-for-SECRET-on-a-persistent-write today. A future ADR settling
this question for real can freely swap which effect this function
returns without touching ``domain/capability.py`` at all. **This also
means ``job_assistance.draft`` is a dynamic-effect capability, not the
static one the design doc first sketched** -- deliberately not
registered in ``build_default_registry()``, mirroring
``memory.write``'s own identical reasoning (see
``kernel/job_assistance.py``'s own docstring).
"""

from __future__ import annotations

from jarvis.domain.capability import Effect
from jarvis.domain.provenance import Classification


def draft_effect_for(classification: Classification) -> Effect:
    """Return the Effect a job_assistance.draft CapabilityInvocation must declare for ``classification``.

    Args:
        classification: The real classification of the drafting
            task's own input text.

    Returns:
        ``Effect.MEMORY_WRITE`` for ``Classification.SECRET`` -- see
        this module's own docstring for why this is a real,
        conservative implementation default, not a settled policy
        decision. ``Effect.WRITE_LOCAL`` for everything else
        (``PUBLIC``, ``PERSONAL``, ``SENSITIVE``) -- the ordinary
        local-write floor (``Tier.CONFIRM``), matching every other
        real classification function in this codebase
        (``memory_effect_for``, ``egress_effect_for``).
    """  # noqa: E501
    if classification is Classification.SECRET:
        return Effect.MEMORY_WRITE
    return Effect.WRITE_LOCAL
