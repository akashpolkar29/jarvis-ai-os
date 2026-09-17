"""Mechanical enforcement (WP-204): workflow composition cannot recurse, at any real depth.

**Real, direct investigation, confirmed before writing this test, not
assumed**: two independent, structural properties together make
recursive/cyclic workflow composition impossible today, not merely
absent from the current registry's contents.

1. ``kernel.capability_dispatch.PLAN_STEP_EXECUTORS`` -- the one, real
   dispatch table both ``application/workflow/composer.py``'s
   ``execute_plan`` call (via ``kernel.workflows.authorize_and_run_workflow``)
   and ``planning.run_plan`` ever consult for a runnable step -- has no
   entry capable of invoking ``authorize_and_run_workflow``,
   ``authorize_and_create_task``, or ``authorize_and_run_task`` (the
   three real functions that could otherwise start a *second* workflow
   run, directly or via a WP-203 workflow-backed task).
   ``kernel/capability_dispatch.py`` was checked directly: it imports
   only from ``application.planning.executor``, ``kernel.capabilities``,
   ``kernel.desktop``, ``kernel.files``, and ``kernel.memory`` -- never
   ``kernel.workflows``, ``kernel.tasks``, or ``kernel.planning``. A
   workflow step can only ever name a ``CapabilityId``
   (:class:`~jarvis.domain.workflow.WorkflowStep`), and every real,
   wired executor is a fixed, safe, ``Tier.ALLOW`` leaf capability
   (``fs.read_file``, ``fs.list_dir``, ``git.status``,
   ``memory.retrieve``, ``fs.find``, ``fs.search_content``,
   ``fs.recent``) -- none of which can create or run a task, or run
   another workflow.

2. ``WorkflowStep``/``WorkflowDescriptor`` (``jarvis.domain.workflow``)
   have no field referencing a :class:`~jarvis.domain.workflow.WorkflowId`
   other than ``WorkflowDescriptor.id`` (its own identity) -- there is
   no "sub-workflow" or "next workflow" field anywhere in the data
   model for a workflow's own steps to name another workflow with, so
   the registry itself cannot represent a cycle, let alone execute one.

Together: a workflow's own steps are a fixed, finite, immutable tuple
(``WorkflowDescriptor.steps``, built once at Python-source registration
time, never user-supplied or mutable at runtime), and nothing reachable
from a step's own execution can ever start another workflow run --
"excessive depth" and "unbounded composition" are not merely
discouraged, they are structurally unreachable. Per this work
package's own instruction ("prefer disallowing recursive workflow
invocation unless there is a demonstrated need... do not
over-engineer"), no new guard code was added -- these tests instead
*prove* the existing architecture already has this property, mirroring
``tests/meta/test_workflows_no_job_search_or_submission_execution.py``'s
own AST-based, docstring-blind, import-only scan exactly for property
(1), and a real dataclass-fields introspection for property (2).
"""

from __future__ import annotations

import ast
import dataclasses

from jarvis.domain.workflow import WorkflowDescriptor, WorkflowId, WorkflowStep
from tests.meta.helpers import SRC_ROOT

_CAPABILITY_DISPATCH_FILE = SRC_ROOT / "jarvis" / "kernel" / "capability_dispatch.py"

_BANNED_IMPORT_MODULE_SUBSTRINGS = (
    "kernel.workflows",
    "kernel.tasks",
    "kernel.planning",
)


def _imported_module_names(source: str) -> set[str]:
    """Return every real module dotted-path referenced by an Import/ImportFrom node."""
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_capability_dispatch_never_imports_workflow_task_or_planning_modules() -> None:
    """No real PlanStepExecutor can ever start a second workflow run, directly or via a task."""
    source = _CAPABILITY_DISPATCH_FILE.read_text(encoding="utf-8")
    modules = _imported_module_names(source)
    for banned in _BANNED_IMPORT_MODULE_SUBSTRINGS:
        matches = {module for module in modules if banned in module}
        assert not matches, (
            f"{_CAPABILITY_DISPATCH_FILE} imports {matches} -- a plan-step executor must "
            "never be able to start another workflow run, directly or via a task."
        )


def test_the_import_ban_actually_detects_a_real_workflows_import() -> None:
    """The predicate genuinely fires on a hypothetical kernel.workflows import."""
    violating_snippet = "from jarvis.kernel.workflows import authorize_and_run_workflow\n"

    modules = _imported_module_names(violating_snippet)

    assert any("kernel.workflows" in module for module in modules)


def test_the_import_ban_actually_detects_a_real_tasks_import() -> None:
    """The predicate genuinely fires on a hypothetical kernel.tasks import."""
    violating_snippet = "import jarvis.kernel.tasks\n"

    modules = _imported_module_names(violating_snippet)

    assert any("kernel.tasks" in module for module in modules)


def test_the_import_ban_does_not_false_positive_on_a_real_memory_import() -> None:
    """A real, legitimate kernel.memory import (unrelated) is never flagged."""
    legitimate_snippet = "from jarvis.kernel.memory import authorize_and_recall\n"

    modules = _imported_module_names(legitimate_snippet)

    assert not any(
        banned in module for module in modules for banned in _BANNED_IMPORT_MODULE_SUBSTRINGS
    )


def test_the_import_ban_ignores_a_docstring_that_merely_discusses_the_guarantee() -> None:
    """Prose naming kernel.workflows in a docstring must not itself be a violation."""
    documentation_only_snippet = (
        '"""This module must never import jarvis.kernel.workflows.\n"""\n\nX = 1\n'
    )

    modules = _imported_module_names(documentation_only_snippet)

    assert not any(
        banned in module for module in modules for banned in _BANNED_IMPORT_MODULE_SUBSTRINGS
    )


def test_workflow_step_has_no_field_naming_another_workflow() -> None:
    """WorkflowStep's own real fields cannot reference a WorkflowId -- proven, not assumed."""
    field_types = {f.name: f.type for f in dataclasses.fields(WorkflowStep)}
    for name, annotation in field_types.items():
        assert "WorkflowId" not in str(annotation), (
            f"WorkflowStep.{name} is annotated {annotation!r} -- a workflow step must never "
            "be able to name another workflow, or composition could recurse."
        )


def test_workflow_descriptor_has_no_workflow_id_field_other_than_its_own_identity() -> None:
    """WorkflowDescriptor's only WorkflowId-typed field is its own id -- no sub-workflow field."""
    field_types = {f.name: f.type for f in dataclasses.fields(WorkflowDescriptor)}
    workflow_id_fields = {
        name for name, annotation in field_types.items() if "WorkflowId" in str(annotation)
    }
    assert workflow_id_fields == {"id"}, (
        f"WorkflowDescriptor has WorkflowId-typed field(s) {workflow_id_fields!r} beyond its "
        "own 'id' -- a real 'sub-workflow' field would let the registry itself represent a "
        "composition cycle."
    )


def test_a_hypothetical_sub_workflow_field_would_be_caught_by_the_field_introspection() -> None:
    """The introspection predicate genuinely fires on a deliberate, synthetic violation."""

    @dataclasses.dataclass(frozen=True)
    class _HypotheticalDescriptorWithASubWorkflow:
        id: WorkflowId
        next_workflow_id: WorkflowId

    field_types = {
        f.name: f.type for f in dataclasses.fields(_HypotheticalDescriptorWithASubWorkflow)
    }
    workflow_id_fields = {
        name for name, annotation in field_types.items() if "WorkflowId" in str(annotation)
    }

    assert workflow_id_fields == {"id", "next_workflow_id"}
