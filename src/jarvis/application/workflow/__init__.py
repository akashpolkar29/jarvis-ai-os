"""M9 workflow layer: safe, deterministic composition of already-existing capabilities.

:func:`~jarvis.application.workflow.composer.compose_workflow` turns a
:class:`~jarvis.domain.workflow.WorkflowDescriptor`'s fixed step
sequence into a real
:class:`~jarvis.application.planning.planner.PlanStep` sequence, ready
for the exact same, unmodified
:func:`~jarvis.application.planning.executor.execute_plan` every other
real plan already uses -- never a second planner, never a second
execution engine. See ``composer.py``'s own module docstring for the
full account, including its real ``Tier.ALLOW``-only halting
behavior.

``kernel/workflows.py`` is the real composition root wiring this
together into the invocable ``workflow.run`` flow.
"""

from __future__ import annotations

from .composer import (
    ComposedWorkflow,
    WorkflowCompositionError,
    compose_workflow,
    resolve_step_arguments,
)

__all__ = [
    "ComposedWorkflow",
    "WorkflowCompositionError",
    "compose_workflow",
    "resolve_step_arguments",
]
