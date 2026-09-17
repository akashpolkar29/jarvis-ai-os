"""Composing a Workflow's fixed steps into a validated PlanStep sequence, with per-step halting.

:func:`compose_workflow` is the real connection point between the new
workflow layer (:mod:`jarvis.domain.workflow`, WP-182/183) and the
already-existing, unmodified planner/executor stack (ADR-0062,
:mod:`jarvis.application.planning`): a
:class:`~jarvis.domain.workflow.WorkflowDescriptor`'s fixed
``WorkflowStep`` sequence is a deterministic, hand-authored
alternative to :func:`~jarvis.application.planning.planner.generate_plan`'s
own reasoning-generated one -- both produce the exact same
:class:`~jarvis.application.planning.planner.PlanStep` type, which then
flows into the exact same, unmodified
:func:`~jarvis.application.planning.executor.execute_plan`. This
module never runs anything itself.

**Safe composition, not a second planner or a second execution
engine**: every step is still individually authorized by
``execute_plan``, exactly as ADR-0062 requires -- this module only
ever decides *which prefix* of a workflow's steps is even eligible to
be handed to ``execute_plan`` at all. A step whose capability is not
registered, has no plan-step executor wired, or whose real, static
tier is above ``Tier.ALLOW`` is never included in ``runnable_steps``:
it becomes the workflow's ``halted_step``, and every step after it is
reported, unexecuted, as ``remaining_steps`` -- mirroring
``application/planning/executor.py``'s own ``Tier.ALLOW``-only ceiling
exactly, and never silently skipping ahead to a later step that might
depend on the halted one's own effect.

**WP-194, closing one real, empirically-confirmed input-validation
gap, not assumed**: a caller-supplied parameter key that names none of
``descriptor.parameters`` was previously silently accepted and simply
never used -- confirmed live before fixing, not assumed: a typo'd key
(e.g. ``"siet"`` instead of ``"site"``) for a *halted* workflow's own
later steps produced no error at all, since
:func:`resolve_step_arguments` only ever checks a placeholder it
actually encounters, and a halted step's own placeholders are never
even reached. :func:`validate_workflow_parameters` closes this by
checking every *supplied* key against the workflow's own declared
``parameters`` up front, in :func:`compose_workflow`, before any step
is touched. **Deliberately not a completeness check**: an omitted,
genuinely-required parameter for a step that never runs (because the
workflow halts before reaching it) is not an error here -- requiring
every declared parameter up front, including ones only a halted,
manually-invoked step would ever need, would add real friction with no
real safety benefit, since that step is never auto-executed regardless.
A parameter actually needed by a *runnable* step is still caught
exactly as before, by :func:`resolve_step_arguments` itself, when that
step is reached.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.application.planning.planner import PlanStep
from jarvis.domain.capability import Tier, minimum_tier_for

if TYPE_CHECKING:
    from collections.abc import Mapping

    from jarvis.application.policy import AuthorizationOrchestrator
    from jarvis.domain.capability import CapabilityId
    from jarvis.domain.workflow import WorkflowDescriptor, WorkflowStep


class WorkflowCompositionError(Exception):
    """Raised when a workflow step's arguments reference an unknown, un-supplied parameter."""


@dataclass(frozen=True)
class ComposedWorkflow:
    """The real, structural outcome of composing one workflow against the live registries.

    Attributes:
        runnable_steps: The ordered, ``Tier.ALLOW``-only prefix of the
            workflow's steps, already converted to real
            :class:`~jarvis.application.planning.planner.PlanStep`
            instances with every ``"${name}"`` placeholder resolved --
            ready to hand to ``execute_plan`` completely unmodified.
        halted_step: The first step this workflow cannot be
            auto-executed past -- its capability is unregistered, has
            no plan-step executor wired, or requires above
            ``Tier.ALLOW``. ``None`` means every step in the workflow
            was runnable.
        remaining_steps: Every step after ``halted_step``, in order,
            never attempted -- present for reporting only ("this
            workflow requires manual/interactive invocation of X, then
            Y, Z remain"), never executed by this module or by
            ``execute_plan``.
    """

    runnable_steps: tuple[PlanStep, ...]
    halted_step: WorkflowStep | None
    remaining_steps: tuple[WorkflowStep, ...]


def resolve_step_arguments(step: WorkflowStep, parameters: Mapping[str, str]) -> dict[str, object]:
    """Resolve ``step.arguments``' ``"${name}"`` placeholders against ``parameters``.

    A string argument value of the exact form ``"${name}"`` is
    replaced by ``parameters[name]``; every other value (including a
    string that merely contains ``${...}`` as a substring) is carried
    through verbatim -- deliberately the smallest possible
    substitution rule, not a templating engine.

    Args:
        step: The workflow step whose arguments to resolve.
        parameters: The caller-supplied parameter values, keyed by
            name.

    Returns:
        A new, plain ``dict`` with every placeholder resolved.

    Raises:
        WorkflowCompositionError: If a placeholder names a parameter
            not present in ``parameters``.
    """
    resolved: dict[str, object] = {}
    for key, value in step.arguments.items():
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            name = value[2:-1]
            if name not in parameters:
                msg = (
                    f"Step {step.description!r} references parameter {name!r}, "
                    "which was not supplied."
                )
                raise WorkflowCompositionError(msg)
            resolved[key] = parameters[name]
        else:
            resolved[key] = value
    return resolved


def validate_workflow_parameters(
    descriptor: WorkflowDescriptor, parameters: Mapping[str, str]
) -> None:
    """Reject any supplied parameter key that names none of ``descriptor``'s own real parameters.

    A real, minimal, explicit "no arbitrary/unrecognized input" check
    -- not a completeness check (see module docstring for why a
    missing, genuinely-required parameter is deliberately left to
    :func:`resolve_step_arguments`'s own, later, per-step check
    instead).

    Args:
        descriptor: The real, already-registered workflow to validate
            ``parameters`` against.
        parameters: Caller-supplied parameter values, keyed by name.

    Raises:
        WorkflowCompositionError: If any key in ``parameters`` is not
            one of ``descriptor.parameters``.
    """
    unknown = sorted(set(parameters) - set(descriptor.parameters))
    if unknown:
        msg = (
            f"Workflow {descriptor.id} does not declare parameter(s) {unknown!r} -- "
            f"real parameters are {list(descriptor.parameters)!r}."
        )
        raise WorkflowCompositionError(msg)


def compose_workflow(
    descriptor: WorkflowDescriptor,
    parameters: Mapping[str, str],
    orchestrator: AuthorizationOrchestrator,
    executors: Mapping[CapabilityId, object],
) -> ComposedWorkflow:
    """Partition ``descriptor``'s steps into an auto-executable prefix and a halted remainder.

    Args:
        descriptor: The real, already-registered workflow to compose.
        parameters: Caller-supplied values for this workflow's own
            ``"${name}"`` placeholders.
        orchestrator: Used only for its ``is_registered``/
            ``get_descriptor`` read-only lookups -- no authorization
            happens here; each runnable step's real authorization
            happens later, inside ``execute_plan``.
        executors: Maps a capability id to whatever real dispatch
            entry ``execute_plan`` will use to run it (real callers
            pass ``jarvis.kernel.capability_dispatch.PLAN_STEP_EXECUTORS``
            -- this module only ever checks membership, never calls
            anything in it, so its value type is opaque here).

    Returns:
        A :class:`ComposedWorkflow` -- see its own docstring.

    Raises:
        WorkflowCompositionError: If ``parameters`` contains a key
            :func:`validate_workflow_parameters` rejects, or a step
            before the halt point references an unresolved placeholder
            (see :func:`resolve_step_arguments`).
    """
    validate_workflow_parameters(descriptor, parameters)

    runnable: list[PlanStep] = []
    halted_step: WorkflowStep | None = None
    remaining: list[WorkflowStep] = []

    for step in descriptor.steps:
        if halted_step is not None:
            remaining.append(step)
            continue

        if step.capability_id not in executors or not orchestrator.is_registered(
            step.capability_id
        ):
            halted_step = step
            continue

        tier = minimum_tier_for(orchestrator.get_descriptor(step.capability_id).effects)
        if tier != Tier.ALLOW:
            halted_step = step
            continue

        arguments = resolve_step_arguments(step, parameters)
        runnable.append(PlanStep(capability_id=step.capability_id, arguments=arguments))

    return ComposedWorkflow(
        runnable_steps=tuple(runnable),
        halted_step=halted_step,
        remaining_steps=tuple(remaining),
    )
