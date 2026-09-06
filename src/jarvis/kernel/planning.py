"""The composition root for planning.run_plan: ADR-0062/M7 task planning, made invocable.

:func:`authorize_and_run_plan` mirrors
:func:`~jarvis.kernel.coding.authorize_and_run_coding_task`'s own
registry/storage/confirmation/orchestrator wiring exactly:
``orchestrator.authorize_by_id()`` first (the outer gate on invoking
the planner at all), the real work only ever inside
``if decision.granted:``, ``storage.save(chain)`` in a ``finally``
block so a granted decision is never lost even if plan generation or
execution itself raises.

**``planning.run_plan`` is a static, fixed-effect capability**
(``Effect.EXECUTE``, ``Tier.CONFIRM`` -- ``kernel/capabilities.py``),
mirroring ``coding.run_task``'s own outer-gate shape exactly. **This is
deliberately a second, separate authorization layer from every real
plan step's own individual authorization** (ADR-0062's own core
decision, executed by ``application/planning/executor.py``) -- a
granted ``planning.run_plan`` only means "the planner may run at all
and propose/attempt a plan"; whether any specific step it proposes is
itself granted is decided later, independently, per step, exactly as
ADR-0062 requires. No batch pre-approval anywhere in this chain: the
outer gate's own `Tier.CONFIRM` does not, and structurally cannot,
pre-authorize what a not-yet-generated plan will contain.

**Local-only default provider, mirroring ``coding.run_task``'s own
identical reasoning**: no real cloud-provider default is invented
here -- inventing one (which vendor-family adapter, which model, which
keyring secret reference) is undecided policy this codebase does not
make anywhere. A caller wanting a different real provider passes one
explicitly.

**Real, honest addendum (2026-09-05, adversarial-verification follow-up)**:
`kernel/coding.py`/`kernel/job_assistance.py` were checked directly
before making this change -- neither has any real credential-auto-
detection mechanism at all; both are purely explicit-override, always
defaulting to local when no provider is supplied. There is nothing to
"prefer cloud when configured" against, since this codebase has no
way to detect that. The real, honest change made here instead: when
the default (local) path is taken, a real
``logging.getLogger(__name__).warning(...)`` call surfaces plainly
that cloud reasoning was not requested and plan generation may be
unreliable as a result -- citing the real, empirically-measured ~33%
local-model failure rate found during ADR-0062's own adversarial
verification pass. The explicit ``provider`` override remains the
only real way to use cloud reasoning, unchanged in shape from before
this addendum; a caller that supplies one sees no warning at all.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.adapters.reasoning.local import LocalReasoningAdapter
from jarvis.application.planning.executor import execute_plan
from jarvis.application.planning.planner import generate_plan
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.capabilities import PLANNING_RUN_PLAN_CAPABILITY_ID, build_default_registry
from jarvis.kernel.capability_dispatch import PLAN_STEP_EXECUTORS

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.application.planning.executor import PlanExecutionResult
    from jarvis.domain.policy import Decision
    from jarvis.ports.reasoning import ReasoningPort

_logger = logging.getLogger(__name__)


async def authorize_and_run_plan(
    goal: str,
    provider: ReasoningPort | None = None,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
) -> tuple[Decision, PlanExecutionResult | None]:
    """Wire up the stack, authorize invoking the planner, and run its plan only if granted.

    Args:
        goal: The real, natural-language goal, typed or spoken
            directly by the user -- wrapped as
            ``Tainted(goal, Provenance.user())``, matching every other
            directly-typed/spoken argument in this codebase.
        provider: The real ``ReasoningPort`` asked to propose a plan.
            Defaults to a real, credential-free ``LocalReasoningAdapter``
            -- see module docstring for why only the *local* default
            exists, not a cloud one. Taking this default logs a real,
            honest warning (see module docstring's own addendum) --
            pass an explicit cloud-backed provider to use real cloud
            reasoning and avoid it.
        physical_confirmation_available: Whether a human is physically
            present, passed straight through both to the outer gate's
            own ``ManualConfirmationAdapter`` and to every real plan
            step's own, separate authorization.
        remote_confirmation_available: As above.
        chain_path: Where the audit chain is persisted -- every real
            decision this call makes (the outer gate, and every real
            plan step's own authorization) lands in this same,
            single, tamper-evident file.

    Returns:
        ``(decision, result)`` -- ``decision`` is the outer
        ``planning.run_plan`` gate's own real ``Decision``, always
        durably appended to the chain by the time this returns.
        ``result`` is ``execute_plan``'s own real
        ``PlanExecutionResult`` if the outer gate was granted, ``None``
        if denied -- the planner never runs at all on a denied outer
        gate, not even plan generation.

    Raises:
        jarvis.application.planning.planner.PlanningError: If the
            provider's proposed plan fails real, structural validation
            (malformed JSON, an unregistered capability). Raised only
            if the outer gate was granted; the outer decision is still
            durably saved before this propagates.
        jarvis.application.planning.executor.PlanValidationError: If a
            structurally-valid plan names a capability with no
            registered executor, or one whose real, static tier is
            above this implementation's ``Tier.ALLOW``-only ceiling
            (see ``executor.py``'s own module docstring for why).
    """
    registry = build_default_registry()
    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(chain, registry, confirmation=confirmation)

    decision = orchestrator.authorize_by_id(
        PLANNING_RUN_PLAN_CAPABILITY_ID,
        Tainted({"goal": goal}, Provenance.user()),
        orchestrator.get_current_context(),
    )
    # Saved immediately, before any real plan step's own, separately-
    # constructed dispatch call loads and re-saves this same file (see
    # capability_dispatch.py's own module docstring): each step
    # sequentially loads-appends-saves chain_path on its own, so the
    # outer gate's decision must already be on disk before the first
    # step's own load() runs, or that step's own save() would never
    # have seen it. A single final save() here, after every step has
    # already run its own, would instead *overwrite* every step's own
    # already-persisted record with this function's own stale,
    # outer-decision-only in-memory copy -- a real bug caught during
    # implementation, not a hypothetical one.
    storage.save(chain)

    result: PlanExecutionResult | None = None
    if decision.granted:
        if provider is None:
            _logger.warning(
                "planning.run_plan: no cloud reasoning provider was supplied -- falling back "
                "to the local model for plan generation. This is a real, known reliability "
                "gap, not a hypothetical one: an adversarial-verification pass (2026-09-05) "
                "measured an empirical ~33 percent real failure rate for this local model on "
                "plan generation, even for a single-capability goal. Pass an explicit, real "
                "cloud-backed ReasoningPort to avoid this."
            )
        real_provider = provider or LocalReasoningAdapter()
        steps = await generate_plan(
            Tainted(goal, Provenance.user()), real_provider, orchestrator.is_registered
        )
        result = execute_plan(
            steps,
            orchestrator,
            PLAN_STEP_EXECUTORS,
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=chain_path,
        )

    return decision, result
