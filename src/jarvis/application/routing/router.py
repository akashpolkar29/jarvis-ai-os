"""Reasoning-fallback structured routing for WP-104's typed freeform command router.

This module is Stage B of the router only. Stage A (deterministic
routing) reuses `jarvis.kernel.intent.resolve_intent()` directly and
lives in `jarvis.kernel.router` -- it cannot live here, since it
depends on `jarvis.kernel.capabilities`/`jarvis.kernel.job_search`/
`jarvis.kernel.music`, and `application` may not depend on `kernel`
(C1, the layered-architecture contract `lint-imports` enforces).

:func:`generate_route` mirrors `application/planning/planner.py`'s own
`generate_plan` shape exactly, on purpose: build a prompt, call the
already-existing `ReasoningPort` (no new port), `json.loads` the
response, validate it structurally, raise on anything malformed. A
capability id the model names is checked against a caller-supplied
`is_registered` predicate -- real callers pass a live
`CapabilityRegistry`'s own `__contains__` (`jarvis.kernel.router`),
the same real mechanism `generate_plan` already uses via
`AuthorizationOrchestrator.is_registered`, so the model can never
invent an unregistered capability id and have it survive validation.

**The router never executes anything, at any stage.** This module
only ever returns a :class:`RouteResult` -- a structured description
of what the input looks like and where it should go. Turning a
`DETERMINISTIC_COMMAND` route into a real, authorized action (and
deciding *whether* it is safe to act on at all) is
`jarvis.kernel.router`'s own, separate job, mirroring this project's
own established "generation and validation are one concern, execution
and authorization are another" separation
(`application/planning/planner.py` vs `application/planning/executor.py`).

**Confidence is never model-supplied, on purpose.** WP-104's own
requirement (section 8: "Do not overtrust confidence... a model saying
confidence=0.99 must never automatically execute something dangerous")
is satisfied structurally here, not just by policy: the JSON schema
this module asks the model to produce has no `confidence` field at
all, so there is nothing for a model to inflate. `RouteResult.confidence`
is instead a fixed, real constant assigned in code
(`_REASONING_ROUTE_CONFIDENCE` below; `jarvis.kernel.router` uses its
own fixed constant for Stage A) -- informational only, never itself
consulted by any authorization decision. Actual authorization always
comes from the real policy/capability system downstream, exactly as
required.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from jarvis.domain.capability import CapabilityId
from jarvis.domain.provenance import Provenance, Tainted

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from jarvis.domain.evidence import Attempt
    from jarvis.ports.reasoning import ReasoningPort


class RoutingError(Exception):
    """Raised when a provider's proposed route fails real, structural validation.

    Covers every real failure mode this module checks for: malformed
    JSON, a response that isn't a single JSON object, an unrecognized
    `kind`, a `DETERMINISTIC_COMMAND` naming a capability id that is
    not a string or not actually registered, non-object `arguments`,
    or a `COMPLEX_GOAL` with an empty/missing `goal`. A malformed
    fallback response is never silently coerced into a guess -- see
    this module's own docstring.
    """


class RouteKind(Enum):
    """What kind of request a route describes.

    Deliberately three, not the prompt's own suggested four --
    `HELP` was considered and rejected: no real help/documentation
    system exists anywhere in this codebase for a `HELP` route to
    hand off to, and inventing one is explicitly out of WP-104's own
    scope (section 17). Adding an unused route kind now would be
    exactly the "don't blindly copy" mistake WP-104's own prompt warns
    against.
    """

    DETERMINISTIC_COMMAND = "deterministic_command"
    """A specific, already-registered capability was identified."""

    COMPLEX_GOAL = "complex_goal"
    """A real, natural-language goal needing task/planner handling, not one capability call."""

    UNKNOWN = "unknown"
    """Neither stage could confidently determine what was being asked."""


@dataclass(frozen=True)
class RouteResult:
    """A structured description of what one piece of typed input looks like, and where it goes.

    Deliberately does not carry separate `task_required`/
    `reasoning_required` booleans the way the prompt's own illustrative
    schema sketch suggested -- both are already fully implied by
    `kind`/`source` (`kind == COMPLEX_GOAL` means task handling is
    needed; `source == "reasoning"` means reasoning was used), and a
    second, independent flag that could drift out of sync with `kind`/
    `source` would be a real, avoidable bug surface, not a useful
    addition.

    Attributes:
        kind: What kind of request this is.
        original_input: The real, original typed text this route was
            produced for, verbatim -- kept for logging/display, never
            re-parsed.
        confidence: A real, fixed, informational-only number (never
            model-supplied -- see module docstring). Not consulted by
            any authorization decision.
        source: `"deterministic"` or `"reasoning"` -- which stage
            produced this route.
        capability_id: The real, already-registered capability this
            route names, if `kind == DETERMINISTIC_COMMAND`. `None`
            otherwise.
        arguments: That capability's own real arguments, in the same
            `Tainted` shape `AuthorizationOrchestrator.authorize_by_id()`
            expects, if `kind == DETERMINISTIC_COMMAND`. `None`
            otherwise.
        goal: The real, natural-language goal text, if
            `kind == COMPLEX_GOAL`. `None` otherwise.
        detail: A real, human-readable explanation, set whenever
            `kind == UNKNOWN` (why neither stage could resolve this,
            e.g. an ambiguous job-search site clause) -- see
            `jarvis.kernel.router`'s own module docstring. `None` when
            not applicable.
    """

    kind: RouteKind
    original_input: str
    confidence: float
    source: str
    capability_id: CapabilityId | None = None
    arguments: Tainted[Mapping[str, object]] | None = None
    goal: str | None = None
    detail: str | None = None


_REASONING_ROUTE_CONFIDENCE = 0.5
"""A fixed, real, informational-only confidence for every reasoning-sourced route.
Never model-supplied -- see module docstring."""

_ROUTING_PROMPT_TEMPLATE = """You are routing a typed request, not executing it. Decide what
kind of request this is and respond with ONLY a single JSON object, no other text.

The object must have exactly these keys:
"kind": one of "deterministic_command", "complex_goal", or "unknown".
"capability_id": a string naming one already-registered capability id (e.g. "fs.read_file"),
    required only when kind is "deterministic_command", otherwise null.
"arguments": a JSON object of that capability's own arguments, required only when kind is
    "deterministic_command", otherwise an empty object.
"goal": a plain-text restatement of the user's real goal, required only when kind is
    "complex_goal", otherwise null.

Use "deterministic_command" only when you are confident the request maps to one specific,
already-existing capability. Use "complex_goal" for a real, multi-step objective that needs
planning. Use "unknown" whenever you are not genuinely confident -- never guess a dangerous or
irreversible action.

Request: {text}
"""


def _build_routing_prompt(text: str) -> str:
    """Build the real, routing-specific prompt text sent to a `ReasoningPort` provider."""
    return _ROUTING_PROMPT_TEMPLATE.format(text=text)


def _parse_route(
    raw: object, original_input: str, is_registered: Callable[[CapabilityId], bool]
) -> RouteResult:
    """Parse and validate one raw, JSON-decoded routing response into a real `RouteResult`.

    Raises:
        RoutingError: If `raw` fails any real, structural check -- see
            `RoutingError`'s own docstring for the full list.
    """
    if not isinstance(raw, dict):
        msg = f"Provider's response must be a JSON object, got {type(raw).__name__}."
        raise RoutingError(msg)

    raw_kind = raw.get("kind")
    try:
        kind = RouteKind(raw_kind)
    except ValueError as exc:
        msg = f"'kind' must be one of {[k.value for k in RouteKind]!r}, got {raw_kind!r}."
        raise RoutingError(msg) from exc

    if kind == RouteKind.DETERMINISTIC_COMMAND:
        raw_capability_id = raw.get("capability_id")
        raw_arguments = raw.get("arguments")
        if not isinstance(raw_capability_id, str):
            msg = f"'capability_id' must be a string, got {raw_capability_id!r}."
            raise RoutingError(msg)
        if not isinstance(raw_arguments, dict):
            msg = f"'arguments' must be a JSON object, got {raw_arguments!r}."
            raise RoutingError(msg)
        capability_id = CapabilityId(raw_capability_id)
        if not is_registered(capability_id):
            msg = f"Provider named {capability_id!r}, which is not a registered capability."
            raise RoutingError(msg)
        return RouteResult(
            kind=kind,
            original_input=original_input,
            confidence=_REASONING_ROUTE_CONFIDENCE,
            source="reasoning",
            capability_id=capability_id,
            arguments=Tainted(raw_arguments, Provenance.user()),
        )

    if kind == RouteKind.COMPLEX_GOAL:
        raw_goal = raw.get("goal")
        if not isinstance(raw_goal, str) or not raw_goal.strip():
            msg = f"'goal' must be a non-empty string for 'complex_goal', got {raw_goal!r}."
            raise RoutingError(msg)
        return RouteResult(
            kind=kind,
            original_input=original_input,
            confidence=_REASONING_ROUTE_CONFIDENCE,
            source="reasoning",
            goal=raw_goal.strip(),
        )

    return RouteResult(
        kind=RouteKind.UNKNOWN,
        original_input=original_input,
        confidence=_REASONING_ROUTE_CONFIDENCE,
        source="reasoning",
        detail="The reasoning fallback could not confidently determine this request.",
    )


async def generate_route(
    text: Tainted[str],
    provider: ReasoningPort,
    is_registered: Callable[[CapabilityId], bool],
) -> RouteResult:
    """Ask `provider` to propose a route for `text`, then validate it structurally.

    Args:
        text: The real, typed/spoken text to route. Its own `Tainted`
            value is what's sent to the provider; its `Provenance` is
            not consulted here, mirroring `generate_plan`'s identical
            treatment of `goal`.
        provider: The real `ReasoningPort` asked to propose a route.
            No new port -- the same one `Dispatcher`/`generate_plan`
            already use.
        is_registered: Checks whether a `CapabilityId` is a real,
            currently-registered capability. Real callers
            (`jarvis.kernel.router`) pass a live `CapabilityRegistry`'s
            own `__contains__`. A route naming an unregistered
            capability is a real routing failure, never silently
            dropped or coerced -- the exact same discipline
            `generate_plan` already applies.

    Returns:
        A real, structurally-valid `RouteResult` with `source="reasoning"`.

    Raises:
        RoutingError: If the provider's response is not valid JSON, or
            fails any of `_parse_route`'s own real, structural checks.
    """
    prior_attempts: tuple[Attempt, ...] = ()
    candidate = (await provider.generate(_build_routing_prompt(text.value), prior_attempts)).value

    try:
        raw_route = json.loads(candidate.content)
    except json.JSONDecodeError as exc:
        msg = f"Provider's response is not valid JSON: {exc}"
        raise RoutingError(msg) from exc

    return _parse_route(raw_route, text.value, is_registered)
