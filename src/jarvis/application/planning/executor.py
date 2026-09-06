"""Real, per-step plan execution for `planning.run_plan` (ADR-0062, M7 design).

:func:`execute_plan` is ADR-0062's own core decision, made real: no
plan is ever authorized as a whole. Every step is authorized
individually, exactly when it runs, via a caller-supplied mapping of
:class:`PlanStepExecutor` callables. This module defines the
contract (:class:`PlanStepOutcome`, the executor callable's own
shape) but never constructs a real one itself -- reusing an
already-existing, unmodified `authorize_and_*` composition function
per capability is `jarvis.kernel.capability_dispatch`'s own real job
(see that module's own docstring for why a generic dispatch registry,
not a `Dispatcher` change, closes the real "authorize_by_id() alone
never performs a real action" gap). **This module never imports
`jarvis.kernel`** -- `application` may not depend on `kernel`
(C1, the layered-architecture contract `lint-imports` enforces); the
real executor mapping is injected by `kernel/planning.py`, the actual
composition root, exactly like every other port/adapter dependency in
this codebase.

**A real, honest, load-bearing restriction found during
implementation, narrower than ADR-0062's own stated ceiling**:
ADR-0062 permits `Tier.ALLOW`/`Tier.CONFIRM` steps in a first version.
This implementation restricts further, to **`Tier.ALLOW` only**, for a
real, concrete reason discovered while wiring the dispatch registry,
not a hypothetical one: every existing `authorize_and_*` function
hardcodes its own arguments' `Provenance` internally (e.g.
`authorize_and_read_file` always wraps its path as
`Tainted(..., Provenance.user())`) -- there is no seam for a caller to
inject a different, more cautious `Provenance` reflecting that a plan
step's arguments actually came from a model-generated plan
(`m7-task-planning-design.md`'s own "Real, open sub-questions" #3 says
this should be `Trust.UNTRUSTED_EXTERNAL`-tagged). For `Tier.ALLOW`
capabilities this has no real behavioral consequence --
`domain/policy.py::evaluate()` hardcodes `granted=True` for
`Tier.ALLOW` regardless of classification, so the wrong `Provenance`
being used internally cannot change the outcome. For `Tier.CONFIRM`
(or any capability whose real classification-sensitive dynamic-effect
resolution cares about content, the way `memory.write`'s own does),
using the wrong, too-permissive `Provenance` could silently
under-classify genuinely model-influenced content. Closing this
properly (threading a real, correct `Provenance` through every
`authorize_and_*` function this dispatch registry might ever wrap)
is real, separate, invasive future work -- not attempted here.
**Every capability currently in `PLAN_STEP_EXECUTORS` is `Tier.ALLOW`,
so this restriction costs nothing today**; it exists to keep a future
`Tier.CONFIRM` addition to that registry from silently reintroducing
this exact gap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.domain.capability import Tier, minimum_tier_for

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from jarvis.application.planning.planner import PlanStep
    from jarvis.application.policy import AuthorizationOrchestrator
    from jarvis.domain.capability import CapabilityId
    from jarvis.domain.policy import Decision

    PlanStepExecutor = Callable[[Mapping[str, object], bool, bool, Path], "PlanStepOutcome"]


@dataclass(frozen=True)
class PlanStepOutcome:
    """One real plan step's outcome: its `Decision`, plus the wrapped function's own real result.

    Attributes:
        decision: The real `Decision` the wrapped `authorize_and_*`
            function itself produced.
        result: That function's own full return value (its own
            `*Outcome` dataclass) -- kept opaque here (`object`) since
            every wrapped function returns a differently-shaped real
            type; a caller that needs the real content inspects
            `result` knowing which capability it asked for.
    """

    decision: Decision
    result: object


class PlanValidationError(Exception):
    """Raised when a plan fails real, pre-flight structural validation.

    Raised before any step is authorized or run -- covers a step
    naming a capability with no registered executor, or a capability
    whose real, static tier exceeds this implementation's own
    `Tier.ALLOW`-only ceiling (see this module's own docstring for
    why this is narrower than ADR-0062's stated `Tier.CONFIRM`
    ceiling).
    """


@dataclass(frozen=True)
class PlanStepRecord:
    """One real, executed plan step's own outcome.

    Attributes:
        step: The `PlanStep` this record is for.
        decision: The real `Decision` produced authorizing this step.
        result: The wrapped `authorize_and_*` function's own full,
            real return value if `decision.granted`, `None` if denied.
    """

    step: PlanStep
    decision: Decision
    result: object | None


@dataclass(frozen=True)
class PlanExecutionResult:
    """The real, complete outcome of running a validated plan, step by step.

    Attributes:
        step_records: Every step actually attempted, in order, each
            with its own real `Decision` -- durably appended to the
            audit chain at `chain_path`, one record per step, by the
            time this returns. Stops at the first denied step; steps
            after that point were never attempted (not present here).
        aborted: Whether execution stopped before every step ran (a
            step was denied). `False` means every step ran and every
            one was granted.
    """

    step_records: tuple[PlanStepRecord, ...]
    aborted: bool


def _validate_plan(
    steps: tuple[PlanStep, ...],
    orchestrator: AuthorizationOrchestrator,
    executors: Mapping[CapabilityId, PlanStepExecutor],
) -> None:
    """Real, pre-flight validation of every step, before any step is authorized or run.

    Raises:
        PlanValidationError: If any step names a capability with no
            entry in `executors`, or whose real, static tier is above
            `Tier.ALLOW` (see this module's own docstring).
    """
    for step in steps:
        if step.capability_id not in executors:
            msg = f"No plan-step executor is registered for {step.capability_id!r}."
            raise PlanValidationError(msg)
        descriptor = orchestrator.get_descriptor(step.capability_id)
        tier = minimum_tier_for(descriptor.effects)
        if tier != Tier.ALLOW:
            msg = (
                f"{step.capability_id!r} requires Tier.{tier.name}, above this v1 planner's "
                "Tier.ALLOW-only ceiling -- see executor.py's own module docstring for why."
            )
            raise PlanValidationError(msg)


def execute_plan(  # noqa: PLR0913 -- one per real, real-consequence caller-supplied dependency
    steps: tuple[PlanStep, ...],
    orchestrator: AuthorizationOrchestrator,
    executors: Mapping[CapabilityId, PlanStepExecutor],
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
) -> PlanExecutionResult:
    """Validate, then run, every step in `steps`, in order -- ADR-0062's core decision, made real.

    Args:
        steps: The real, already-structurally-validated plan (see
            `planner.generate_plan`).
        orchestrator: Used only for `get_descriptor`'s own pre-flight
            tier check -- each step's real authorization happens
            inside its own wrapped `authorize_and_*` call, via its own,
            separately-constructed orchestrator (see
            `kernel/capability_dispatch.py`'s own module docstring for
            why).
        executors: Maps a capability id to the real function that
            authorizes and, if granted, performs that capability's own
            real action. Real callers pass
            `kernel.capability_dispatch.PLAN_STEP_EXECUTORS` -- this
            module never imports it directly (`application` may not
            depend on `kernel`, see this module's own docstring).
        physical_confirmation_available: Passed straight through to
            every step's own wrapped `authorize_and_*` call.
        remote_confirmation_available: As above.
        chain_path: Where every step's own real audit record is
            persisted -- the same file for every step, loaded and
            saved once per step.

    Returns:
        A `PlanExecutionResult` -- see its own docstring.

    Raises:
        PlanValidationError: If pre-flight validation fails (see
            `_validate_plan`). No step is authorized or run in this
            case -- not even the first one.
    """
    _validate_plan(steps, orchestrator, executors)

    records: list[PlanStepRecord] = []
    for step in steps:
        executor = executors[step.capability_id]
        outcome = executor(
            step.arguments,
            physical_confirmation_available,
            remote_confirmation_available,
            chain_path,
        )
        result = outcome.result if outcome.decision.granted else None
        records.append(PlanStepRecord(step=step, decision=outcome.decision, result=result))
        if not outcome.decision.granted:
            return PlanExecutionResult(step_records=tuple(records), aborted=True)

    return PlanExecutionResult(step_records=tuple(records), aborted=False)
