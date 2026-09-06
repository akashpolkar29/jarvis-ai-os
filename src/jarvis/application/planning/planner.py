"""Real plan generation and structural validation for `planning.run_plan` (ADR-0062, M7 design).

:func:`generate_plan` is the real implementation of
`docs/architecture/m7-task-planning-design.md`'s own "What structurally
changes" section, steps 1-3: a single, natural-language goal becomes a
real, structurally-validated sequence of :class:`PlanStep`, each naming
an already-registered `CapabilityId` and its own arguments. No new
port -- this calls the existing `ReasoningPort` directly, the same
port `Dispatcher` already uses, with a distinct, planning-specific
prompt.

**What this module does not do**: it never runs a step. Turning a
validated :class:`PlanStep` sequence into real, individually-authorized
capability invocations is `application/planning/executor.py`'s own,
separate job -- mirroring this project's own established "generation
and validation are one concern, execution and authorization are
another" separation (`application/coding/loop.py`'s own
`run_coding_task` vs. `Dispatcher`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.domain.capability import CapabilityId

if TYPE_CHECKING:
    from collections.abc import Callable

    from jarvis.domain.evidence import Attempt
    from jarvis.domain.provenance import Tainted
    from jarvis.ports.reasoning import ReasoningPort


class PlanningError(Exception):
    """Raised when a provider's proposed plan fails real, structural validation.

    Covers every real failure mode this module checks for: malformed
    JSON, a step missing a required field, or a step naming a
    `CapabilityId` that is not actually registered. A planning failure
    is not silently coerced into "close enough" -- see this module's
    own docstring.
    """


@dataclass(frozen=True)
class PlanStep:
    """One real, structurally-validated step: an already-registered capability plus its arguments.

    Attributes:
        capability_id: The capability this step invokes. Guaranteed,
            by the time a `PlanStep` exists, to have been checked
            against the real, live capability registry -- never a
            capability the provider merely claimed exists.
        arguments: This step's own arguments, as a JSON-serializable
            mapping -- not yet wrapped `Tainted`, since the correct
            `Provenance` to wrap them in depends on the *original
            goal's* own provenance, a fact this module does not have
            (see `executor.py`'s own real construction of each step's
            `Tainted` arguments).
    """

    capability_id: CapabilityId
    arguments: dict[str, object]


_PLANNING_PROMPT_TEMPLATE = """You are planning, not executing. Given the goal below, propose an
ordered sequence of steps. Each step must name one already-existing capability id and its
arguments.

Respond with ONLY a JSON array, no other text. Each element must be an object with exactly two
keys: "capability_id" (a string) and "arguments" (a JSON object of that capability's own
arguments).

Example response shape:
[{{"capability_id": "fs.read_file", "arguments": {{"path": "/home/user/notes.txt"}}}}]

Goal: {goal}
"""


def _build_planning_prompt(goal: str) -> str:
    """Build the real, planning-specific prompt text sent to a `ReasoningPort` provider."""
    return _PLANNING_PROMPT_TEMPLATE.format(goal=goal)


def _parse_step(raw: object) -> PlanStep:
    """Parse and validate one raw, JSON-decoded plan-step object.

    Raises:
        PlanningError: If `raw` is not an object with exactly the
            required shape, or its `capability_id` is not a valid
            `CapabilityId` token.
    """
    if not isinstance(raw, dict):
        msg = f"Each plan step must be a JSON object, got {raw!r}."
        raise PlanningError(msg)
    if "capability_id" not in raw or "arguments" not in raw:
        msg = f"Each plan step must have 'capability_id' and 'arguments', got {raw!r}."
        raise PlanningError(msg)
    raw_id = raw["capability_id"]
    raw_arguments = raw["arguments"]
    if not isinstance(raw_id, str):
        msg = f"'capability_id' must be a string, got {raw_id!r}."
        raise PlanningError(msg)
    if not isinstance(raw_arguments, dict):
        msg = f"'arguments' must be a JSON object, got {raw_arguments!r}."
        raise PlanningError(msg)
    try:
        capability_id = CapabilityId(raw_id)
    except ValueError as exc:
        msg = f"'capability_id' {raw_id!r} is not a valid capability id: {exc}"
        raise PlanningError(msg) from exc
    return PlanStep(capability_id=capability_id, arguments=raw_arguments)


async def generate_plan(
    goal: Tainted[str],
    provider: ReasoningPort,
    is_registered: Callable[[CapabilityId], bool],
) -> tuple[PlanStep, ...]:
    """Ask `provider` to propose a plan for `goal`, then validate it structurally.

    Args:
        goal: The real, natural-language goal to plan for. Its own
            `Tainted` value is what's sent to the provider; its
            `Provenance` is not consulted here -- see `executor.py`
            for how a step's own `Provenance` is later constructed.
        provider: The real `ReasoningPort` asked to propose a plan.
            No new port -- the same one `Dispatcher` already uses.
        is_registered: Checks whether a `CapabilityId` is a real,
            currently-registered capability. Real callers pass
            `AuthorizationOrchestrator.is_registered`; tests pass a
            fake. A step naming an unregistered capability is a real
            planning failure, not silently dropped or coerced.

    Returns:
        A real, ordered, structurally-valid sequence of `PlanStep`.
        Empty if the provider proposes zero steps -- a valid, if
        useless, plan; callers decide whether an empty plan is itself
        an error.

    Raises:
        PlanningError: If the provider's response is not valid JSON,
            is not a JSON array, any element fails `_parse_step`'s own
            validation, or any step names a `CapabilityId` that
            `is_registered` reports as not registered.
    """
    prior_attempts: tuple[Attempt, ...] = ()
    candidate = (await provider.generate(_build_planning_prompt(goal.value), prior_attempts)).value

    try:
        raw_plan = json.loads(candidate.content)
    except json.JSONDecodeError as exc:
        msg = f"Provider's response is not valid JSON: {exc}"
        raise PlanningError(msg) from exc
    if not isinstance(raw_plan, list):
        msg = f"Provider's response must be a JSON array, got {type(raw_plan).__name__}."
        raise PlanningError(msg)

    steps = tuple(_parse_step(raw_step) for raw_step in raw_plan)
    for step in steps:
        if not is_registered(step.capability_id):
            msg = f"Plan step names {step.capability_id!r}, which is not a registered capability."
            raise PlanningError(msg)
    return steps
