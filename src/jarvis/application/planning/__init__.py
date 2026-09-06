"""M7 task planning: ADR-0062's own real "no batch pre-approval" property, made real.

:func:`~jarvis.application.planning.planner.generate_plan` asks a real
`ReasoningPort` provider (no new port) to propose an ordered sequence
of :class:`~jarvis.application.planning.planner.PlanStep`, each naming
an already-registered `CapabilityId`, then validates the response
structurally -- malformed JSON, a missing field, or an unregistered
capability id all raise
:class:`~jarvis.application.planning.planner.PlanningError`.

:func:`~jarvis.application.planning.executor.execute_plan` is
ADR-0062's own core decision, made real: no plan is ever authorized as
a whole. Every step is authorized individually, via
:func:`~jarvis.kernel.capability_dispatch.PLAN_STEP_EXECUTORS`'s own
real dispatch registry, exactly when it runs. A pre-flight check
(:class:`~jarvis.application.planning.executor.PlanValidationError`)
rejects any step naming a capability with no registered executor, or
whose real, static tier is above `Tier.ALLOW` -- narrower than
ADR-0062's own stated `Tier.ALLOW`/`Tier.CONFIRM` ceiling, a real,
additive restriction found during implementation (see
`executor.py`'s own module docstring for why).

`kernel/planning.py`'s own `authorize_and_run_plan` is the real
composition root wiring both together into the invocable
`planning.run_plan` capability.
"""

from __future__ import annotations

from .executor import (
    PlanExecutionResult,
    PlanStepRecord,
    PlanValidationError,
    execute_plan,
)
from .planner import PlanningError, PlanStep, generate_plan

__all__ = [
    "PlanExecutionResult",
    "PlanStep",
    "PlanStepRecord",
    "PlanValidationError",
    "PlanningError",
    "execute_plan",
    "generate_plan",
]
