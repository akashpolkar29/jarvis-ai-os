"""Workflows: a named, deterministic composition of existing operations, above Skills.

A :class:`WorkflowDescriptor` is pure, static, "what does this do, in
what order" metadata -- identity, a human-readable description, and an
ordered sequence of :class:`WorkflowStep`, each naming one already-
registered :class:`~jarvis.domain.capability.CapabilityId` and its own
arguments. A workflow never carries an ``Effect``/``Tier`` of its own
and never executes anything itself: it describes a fixed sequence of
already-existing capability invocations, each of which still goes
through the exact same ``CapabilityDescriptor``/``Effect``/``Tier``/
``AuthorizationOrchestrator`` choke point it always did (WP-182, M9
workflow layer scoping).

**Why this lives in ``domain``, not ``application`` or ``kernel``**:
mirrors :class:`~jarvis.domain.skill.SkillDescriptor` exactly -- pure,
frozen, stdlib-only data describing *what a workflow is*, with no I/O,
no async, no wall-clock/randomness, and no knowledge of how a step is
actually authorized or run (that is
``application/workflow/composer.py``'s and ``kernel/workflows.py``'s
own, separate job).

**What this explicitly does NOT do**: a ``WorkflowStep`` is not itself
authorized or executed by anything in this module -- resolving a
step's argument templates against caller-supplied parameters, checking
each step's real, live tier, and running the resulting sequence
through the existing planner's ``execute_plan`` is deliberately kept
out of ``domain`` (no I/O, no orchestrator access here). This module
also never invents a second planner or a second execution engine: a
workflow is a fixed, hand-authored alternative to
``application/planning/planner.py``'s own reasoning-generated
``PlanStep`` sequence, feeding into the exact same, unmodified
``application/planning/executor.py::execute_plan``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .capability import CapabilityId
    from .skill import SkillId


@dataclass(frozen=True)
class WorkflowId:
    """A validated, simple-token identifier for a workflow.

    Mirrors :class:`~jarvis.domain.skill.SkillId` exactly -- used as a
    dict key, so it must be a single token: non-empty and free of
    whitespace (e.g. ``"job_search_assistant"``, ``"research"``).

    Raises:
        ValueError: If ``value`` is empty or contains whitespace.
    """

    value: str

    def __post_init__(self) -> None:
        """Validate ``value`` is a non-empty, whitespace-free token."""
        if not self.value:
            msg = "WorkflowId must not be empty."
            raise ValueError(msg)
        if any(ch.isspace() for ch in self.value):
            msg = f"WorkflowId must not contain whitespace: {self.value!r}"
            raise ValueError(msg)

    def __str__(self) -> str:
        """Return the underlying token, for log fields and messages."""
        return self.value


@dataclass(frozen=True)
class WorkflowStep:
    """One real, ordered step: an already-existing capability plus its own fixed arguments.

    Attributes:
        capability_id: The capability this step invokes. Only ever
            checked to be a real, registered capability at
            :func:`~jarvis.domain.workflow_registry.validate_workflow_registry`
            time -- this module does not itself consult any
            capability registry.
        arguments: This step's own arguments, as a JSON-serializable
            mapping. A string value of the exact form ``"${name}"``
            is a placeholder, resolved against a caller-supplied
            parameter named ``name`` at run time (see
            ``application/workflow/composer.py``) -- this module does
            not resolve it, only carries it verbatim.
        description: A short, human-readable statement of what this
            step is for, shown in ``jarvis workflow show``. Must be
            non-empty -- an undescribed step is not a documented,
            reviewable composition.
    """

    capability_id: CapabilityId
    arguments: Mapping[str, object]
    description: str

    def __post_init__(self) -> None:
        """Validate ``description`` is non-empty."""
        if not self.description:
            msg = "WorkflowStep.description must not be empty."
            raise ValueError(msg)


@dataclass(frozen=True)
class WorkflowDescriptor:
    """A workflow's static, registered-once metadata: an ordered, named composition.

    Attributes:
        id: The workflow's identifier.
        name: A short, human-readable display name (e.g. "Job Search
            Assistant"). Must be non-empty.
        description: What this workflow accomplishes, shown in
            discovery output. Must be non-empty.
        steps: The ordered sequence of :class:`WorkflowStep` this
            workflow composes. Must be non-empty -- a workflow with no
            steps composes nothing.
        skill_id: The :class:`~jarvis.domain.skill.SkillId` this
            workflow is most closely associated with, if any -- purely
            a discoverability cross-reference, never itself validated
            against a live ``SkillRegistry`` here (workflows remain
            valid even if run standalone, with no skill layer loaded).
        parameters: The named, caller-supplied parameters this
            workflow's own ``"${name}"`` placeholders may reference.
            Defaults to empty (a fully fixed workflow with no
            placeholders).
        metadata: Optional, free-form ``str``-to-``str`` annotations
            (e.g. a source doc reference). Defaults to empty.
    """

    id: WorkflowId
    name: str
    description: str
    steps: tuple[WorkflowStep, ...]
    skill_id: SkillId | None = None
    parameters: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the required text fields and that ``steps`` is non-empty."""
        if not self.name:
            msg = "WorkflowDescriptor.name must not be empty."
            raise ValueError(msg)
        if not self.description:
            msg = "WorkflowDescriptor.description must not be empty."
            raise ValueError(msg)
        if not self.steps:
            msg = (
                "WorkflowDescriptor.steps must not be empty -- a workflow must "
                "compose at least one real step."
            )
            raise ValueError(msg)
