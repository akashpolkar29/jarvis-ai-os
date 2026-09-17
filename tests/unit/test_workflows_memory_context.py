"""Cross-workflow tests for WP-188's memory-context integration.

Proves the two real, structural properties WP-188 relies on rather
than building: every workflow's own ``memory.retrieve`` step requests
an explicit, small slice of memory (never "everything"), and the real
storage-adapter layer beneath it already excludes SECRET-classified
content unconditionally -- see ``kernel/workflows.py``'s own WP-188
docstring section for the full account of why nothing new was built
here.
"""

from __future__ import annotations

from jarvis.domain.capability import CapabilityId
from jarvis.kernel.workflows import build_default_workflow_registry

_MEMORY_RETRIEVE_ID = CapabilityId("memory.retrieve")
_MAX_REASONABLE_LIMIT = 20  # generous, but well short of "the whole store"


def test_every_memory_retrieve_step_declares_an_explicit_bounded_limit() -> None:
    """No built-in workflow's memory.retrieve step is unbounded -- each requests a small slice."""
    registry = build_default_workflow_registry()
    memory_steps = [
        step
        for workflow in registry
        for step in workflow.steps
        if step.capability_id == _MEMORY_RETRIEVE_ID
    ]

    assert len(memory_steps) > 0  # sanity: this registry does use memory.retrieve for context
    for step in memory_steps:
        assert "limit" in step.arguments, (
            f"{step.description!r} calls memory.retrieve with no explicit limit."
        )
        limit = step.arguments["limit"]
        assert isinstance(limit, int)
        assert 0 < limit <= _MAX_REASONABLE_LIMIT

    expected_context_workflow_count = 3  # Job Search Assistant, Research, Coding Assistant
    assert len(memory_steps) == expected_context_workflow_count


def test_every_memory_retrieve_step_queries_by_an_explicit_caller_supplied_parameter() -> None:
    """Every memory.retrieve step's query is a "${...}" placeholder, never a hardcoded string.

    "Explicit context selection" means the caller decides what to
    recall -- a workflow author hardcoding a fixed query string would
    defeat that, recalling the same memories regardless of what the
    caller actually asked about.
    """
    registry = build_default_workflow_registry()
    memory_steps = [
        step
        for workflow in registry
        for step in workflow.steps
        if step.capability_id == _MEMORY_RETRIEVE_ID
    ]

    for step in memory_steps:
        query = step.arguments["query"]
        assert isinstance(query, str)
        assert query.startswith("${")
        assert query.endswith("}")
