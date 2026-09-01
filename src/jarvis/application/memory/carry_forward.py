"""ADR-0050's own real consumer: a recalled record's provenance carried forward, for real.

`docs/threat-model/v0.md`'s own M4 closeout named a real, honest gap:
ADR-0050's carry-forward rule (a recalled `MemoryRecord`'s own real
`Provenance` must be reused, never discarded for a fresh one, when its
value is fed into a *new* `CapabilityInvocation`) was mechanically
enforced (`tests/meta/test_memory_provenance_carryforward.py`) but had
no real caller anywhere in this codebase to actually exercise it.
:func:`authorize_reasoning_call_with_recalled_context` is that real
caller -- the exact worked example ADR-0050's own Decision section
already names: "a future capability... wants to use a recalled
SENSITIVE preference inside a call to a cloud-bound `ReasoningPort`
adapter."

No new `Effect`/`Tier` decision here (ADR-0050's own Consequences
section: "the existing `effective_tier` machinery already does the
right thing once a retrieved record's real provenance is correctly
carried into a new invocation") -- this module's whole job is making
that carrying-forward actually happen, for a real caller, not
inventing new authorization logic.

Deliberately does not reference the `Provenance` class by name (only
`record.value.provenance`, an attribute read) -- the exact "safe,
encouraged pattern" `test_memory_provenance_carryforward.py`'s own
docstring describes, which is why this module needs no allowlist entry
there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jarvis.application.reasoning.router import ModelRouter
    from jarvis.domain.memory import MemoryRecord
    from jarvis.domain.policy import Decision, PolicyContext
    from jarvis.domain.provenance import Tainted
    from jarvis.domain.reasoning import ProviderProfile


def authorize_reasoning_call_with_recalled_context(
    record: MemoryRecord,
    task: Tainted[str],
    profile: ProviderProfile,
    router: ModelRouter,
    context: PolicyContext,
) -> Decision:
    """Authorize a reasoning-provider call whose task combines `task` with a recalled record.

    `record`'s own real, unmodified provenance is carried forward into
    the new `CapabilityInvocation` this builds -- never discarded, and
    never used *alone* either: `task`'s own provenance is real too
    (typically `Provenance.user()`, but a caller-supplied value could
    carry its own real classification), so the two are merged via
    `Tainted.combine()`/`Provenance.merge()` -- "the maximum trust, the
    maximum classification" of the two, per that method's own
    docstring, matching this project's own fail-closed principle
    (this project's own architecture summary: "inherits the highest classification present"). A
    `Classification.SENSITIVE` record recalled here and fed into a
    cloud-bound provider call requires the identical `Tier.CONFIRM`
    gate a live `SENSITIVE` value reaching the same call would -- no
    free pass just because its immediate origin was memory rather than
    a live source (ADR-0050's own stated worked example).

    Args:
        record: A real record already recalled via
            `RetrievalPort.retrieve()`. Never a `Classification.SECRET`
            record -- `RetrievalPort` itself never returns one
            (ADR-0050's own amendment); this function does not, and
            does not need to, re-check that here.
        task: Additional real task content to combine with the
            recalled value, with its own real provenance -- the
            caller's own responsibility to have tagged correctly
            before this call, the same trust boundary every other
            dynamic-effect capability in this codebase already
            carries.
        profile: Which provider this call is against.
        router: Routes the resulting invocation through the real
            `AuthorizationOrchestrator`.
        context: Facts about the environment this decision is made in.

    Returns:
        The real `Decision` -- granted only if the merged, carried-
        forward classification permits this specific provider call,
        exactly as it would for a live value of the same
        classification.
    """
    combined_task = record.value.combine(
        task, lambda recalled, extra: f"{extra}\n\nRecalled context: {recalled}"
    )
    return router.authorize_provider_call(profile, combined_task, context)
