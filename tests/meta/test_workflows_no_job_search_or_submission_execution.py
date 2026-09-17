"""Mechanical enforcement (WP-197): the workflow engine cannot reach job-search/submission code.

**Real, direct finding, confirmed before writing this test, not
assumed**: `kernel/workflows.py::PLAN_STEP_EXECUTORS` usage and
`application/workflow/composer.py` were checked directly -- neither
imports `jarvis.kernel.job_search`, `jarvis.kernel.job_assistance`, or
`jarvis.kernel.job_application` at all. This is a real, *stronger*
guarantee than "the Job Search Assistant workflow's own
`job_search.open_results` step always halts" (already proven by
`test_workflows_job_search.py`): even if a future work package added
a new workflow naming one of those capabilities, the composition/
execution engine itself has no code path capable of invoking any of
them, since `kernel.capability_dispatch.PLAN_STEP_EXECUTORS` (the only
real dispatch table `execute_plan` ever consults) has no entry for any
of the three, and neither module imports their real implementations
at all -- structurally, not merely by today's registry contents.

Mirrors `tests/meta/test_job_search_no_content_reading.py`'s own
AST-based, docstring-blind, import-only scan exactly.
"""

from __future__ import annotations

import ast

from tests.meta.helpers import SRC_ROOT

_WORKFLOW_ENGINE_FILES = (
    SRC_ROOT / "jarvis" / "kernel" / "workflows.py",
    SRC_ROOT / "jarvis" / "application" / "workflow" / "composer.py",
    SRC_ROOT / "jarvis" / "kernel" / "capability_dispatch.py",
)

_BANNED_IMPORT_MODULE_SUBSTRINGS = (
    "kernel.job_search",
    "kernel.job_assistance",
    "kernel.job_application",
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


def test_the_workflow_engine_never_imports_job_search_assistance_or_application_modules() -> None:
    """None of the workflow engine's own real files import job-search/submission-adjacent code."""
    for path in _WORKFLOW_ENGINE_FILES:
        source = path.read_text(encoding="utf-8")
        modules = _imported_module_names(source)
        for banned in _BANNED_IMPORT_MODULE_SUBSTRINGS:
            matches = {module for module in modules if banned in module}
            assert not matches, (
                f"{path} imports {matches} -- the workflow execution engine must never "
                "be able to reach job-search/job-assistance/job-application code."
            )


def test_the_import_ban_actually_detects_a_real_job_search_import() -> None:
    """The predicate genuinely fires on a hypothetical kernel.job_search import."""
    violating_snippet = "from jarvis.kernel.job_search import authorize_and_open_job_search\n"

    modules = _imported_module_names(violating_snippet)

    assert any("kernel.job_search" in module for module in modules)


def test_the_import_ban_actually_detects_a_real_job_application_import() -> None:
    """The predicate genuinely fires on a hypothetical kernel.job_application import."""
    violating_snippet = "import jarvis.kernel.job_application\n"

    modules = _imported_module_names(violating_snippet)

    assert any("kernel.job_application" in module for module in modules)


def test_the_import_ban_does_not_false_positive_on_a_real_tasks_import() -> None:
    """A real, legitimate kernel.tasks import (unrelated) is never flagged."""
    legitimate_snippet = "from jarvis.kernel.tasks import authorize_and_create_task\n"

    modules = _imported_module_names(legitimate_snippet)

    assert not any(
        banned in module for module in modules for banned in _BANNED_IMPORT_MODULE_SUBSTRINGS
    )


def test_the_import_ban_ignores_a_docstring_that_merely_discusses_the_guarantee() -> None:
    """Prose naming kernel/job_search.py in a docstring must not itself be a violation."""
    documentation_only_snippet = (
        '"""This module must never import jarvis.kernel.job_search.\n"""\n\nX = 1\n'
    )

    modules = _imported_module_names(documentation_only_snippet)

    assert not any(
        banned in module for module in modules for banned in _BANNED_IMPORT_MODULE_SUBSTRINGS
    )
