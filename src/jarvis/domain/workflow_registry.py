"""The workflow registry: where a workflow's static metadata becomes lookupable by id.

Mirrors :mod:`jarvis.domain.skill_registry` exactly, on purpose -- an
in-memory, append-only-by-id, no-I/O collection of
:class:`~jarvis.domain.workflow.WorkflowDescriptor`, keyed by
:class:`~jarvis.domain.workflow.WorkflowId`. Registration never
overwrites; a lookup that misses is a loud, specific failure. No
dynamic discovery from disk, no manifest files, no plugin loading --
deferred, real future work, matching
:mod:`jarvis.domain.registry`/:mod:`jarvis.domain.skill_registry`'s
own identical scope note.

:func:`validate_workflow_registry` mirrors
:func:`~jarvis.domain.skill_registry.validate_skill_registry` exactly:
it reuses the existing, real
:class:`~jarvis.domain.registry.CapabilityRegistry` to confirm every
workflow step's ``capability_id`` names something that genuinely
exists, rather than inventing a second, parallel notion of what
capabilities exist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .errors import (
    WorkflowAlreadyRegistered,
    WorkflowNotRegistered,
    WorkflowReferencesUnknownCapability,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .registry import CapabilityRegistry
    from .workflow import WorkflowDescriptor, WorkflowId


class WorkflowRegistry:
    """An in-memory lookup of every currently-known workflow, keyed by id."""

    def __init__(self) -> None:
        """Build an empty registry."""
        self._descriptors: dict[WorkflowId, WorkflowDescriptor] = {}

    def register(self, descriptor: WorkflowDescriptor) -> None:
        """Register ``descriptor`` under its own id.

        Args:
            descriptor: The workflow descriptor to register.

        Raises:
            WorkflowAlreadyRegistered: If a descriptor is already
                registered under ``descriptor.id``. Never overwrites --
                the caller must resolve the collision itself.
        """
        if descriptor.id in self._descriptors:
            msg = f"Workflow {descriptor.id} is already registered."
            raise WorkflowAlreadyRegistered(msg)
        self._descriptors[descriptor.id] = descriptor

    def get(self, workflow_id: WorkflowId) -> WorkflowDescriptor:
        """Look up the descriptor registered under ``workflow_id``.

        Args:
            workflow_id: The id to look up.

        Returns:
            The descriptor registered under ``workflow_id``.

        Raises:
            WorkflowNotRegistered: If no descriptor is registered under
                ``workflow_id``.
        """
        try:
            return self._descriptors[workflow_id]
        except KeyError:
            msg = f"No workflow is registered under {workflow_id}."
            raise WorkflowNotRegistered(msg) from None

    def __contains__(self, workflow_id: WorkflowId) -> bool:
        """Return whether a descriptor is registered under ``workflow_id``."""
        return workflow_id in self._descriptors

    def __len__(self) -> int:
        """Return the number of registered workflows."""
        return len(self._descriptors)

    def __iter__(self) -> Iterator[WorkflowDescriptor]:
        """Iterate over every registered descriptor, each exactly once.

        Iteration order is not part of this class's contract.
        """
        return iter(self._descriptors.values())


def validate_workflow_registry(
    workflows: WorkflowRegistry, capabilities: CapabilityRegistry
) -> None:
    """Confirm every registered workflow's steps name a real, registered capability.

    Args:
        workflows: The workflow registry to validate.
        capabilities: The real capability registry to validate against
            (e.g. ``kernel.capabilities.build_default_registry()``).

    Raises:
        WorkflowReferencesUnknownCapability: If any registered
            workflow has a step naming a capability id that
            ``capabilities`` does not contain. Reused, never a new,
            parallel definition of "exists" -- this is the exact same
            ``CapabilityRegistry.__contains__`` every real
            authorization call already relies on.
    """
    for workflow in workflows:
        for step in workflow.steps:
            if step.capability_id not in capabilities:
                msg = (
                    f"Workflow {workflow.id} step references unknown capability "
                    f"{step.capability_id!r}."
                )
                raise WorkflowReferencesUnknownCapability(msg)
