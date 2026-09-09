"""WP-104: the typed freeform command router -- `jarvis do "<text>"`'s real composition root.

**Product goal, stated precisely**: accept a normal typed
natural-language request rather than requiring the user to know a
specific CLI command, routing it deterministically where a safe,
already-known mapping exists, and falling back to reasoning only for
genuinely unrecognized or complex requests. **This is a router, not an
autonomous agent** -- it identifies what kind of request this is and
where it should go; it never solves a goal itself (searching jobs,
browsing pages, modifying CVs, sending email, filling forms, and
submitting applications all remain out of scope here, exactly as
instructed).

**Stage A (deterministic) reuses `jarvis.kernel.intent.resolve_intent()`
directly, unmodified.** That function is already this codebase's real,
existing source of truth for "text -> capability + arguments" (every
voice command it recognizes: ping/play/pause/next/previous, read,
remember, recall, code, plan, send email, create event, search jobs,
find files, search files, recent files, careers page). Duplicating
that grammar here, even partially, was explicitly ruled out by WP-104's
own prompt ("do not duplicate all command definitions manually if an
existing reusable source of truth can be safely reused"). A small,
real, bounded normalization step (:func:`_normalize_for_deterministic_routing`)
strips a fixed set of conversational filler words/punctuation
("please", "can you", trailing "?"/".") before calling it, covering
WP-104's own named examples ("please open youtube" / "can you open
youtube?") without building a general NLP grammar.

**A real, honest, named limitation**: `resolve_intent()` has no
grammar for "open <a URL/site>" at all -- `kernel/intent.py`'s own
docstring records this as a deliberate voice-grammar omission ("a
spoken URL is low-value and error-prone compared to the CLI"), not an
oversight this work package introduces. "Open YouTube"-shaped requests
therefore resolve to `RouteKind.UNKNOWN` at Stage A and fall through to
Stage B, where the reasoning fallback may or may not itself produce a
real, executable route -- this module does not invent a new
deterministic "open a site" grammar to paper over that gap, since doing
so was never asked for and would be exactly the kind of unbounded
grammar growth this work package's own prompt warns against.

**Stage B (reasoning fallback) is `jarvis.application.routing.router.generate_route`,
called only when Stage A returns `RouteKind.UNKNOWN`.** Mirrors
`authorize_and_run_plan`'s own real, local-only default-provider
reasoning exactly (`kernel/planning.py`'s own module docstring) --
no real cloud-provider default is invented here either; an explicit
`provider` override remains the only way to reach real cloud
reasoning, and the local default path logs the identical, real,
honest reliability warning.

**The router never executes a capability directly, at any stage --
this is a structural property, not just documentation.**
:func:`authorize_and_route` only ever does one of three things once a
real `RouteResult` exists:

1. `RouteKind.DETERMINISTIC_COMMAND` whose `capability_id` is one of
   the (currently four) entries already wired in
   `jarvis.kernel.capability_dispatch.PLAN_STEP_EXECUTORS` -- reuses
   that already-existing, already-tested executor completely
   unmodified, the exact same mechanism `planning.run_plan`'s own
   executor already uses per plan step. Every one of those four is
   `Tier.ALLOW`; the real authorization choke point
   (`AuthorizationOrchestrator`) still evaluates every single call.
2. `RouteKind.DETERMINISTIC_COMMAND` whose `capability_id` is real and
   registered but **not** wired in `PLAN_STEP_EXECUTORS` (e.g. a
   reasoning-sourced route naming `git.force_push`) -- reported back,
   never executed. There is no generic "authorize_by_id, then invoke
   whatever adapter that implies" mechanism anywhere in this codebase
   (`kernel/capability_dispatch.py`'s own module docstring names this
   exact gap), so a capability outside that fixed, small table
   structurally cannot be run from this entry point at all, regardless
   of what tier it is or what the reasoning fallback proposed.
3. `RouteKind.COMPLEX_GOAL` -- creates a new task
   (`jarvis.kernel.tasks.authorize_and_create_task`, WP-107) with
   status `"created"`. **Does not run it.** Running a task is its own,
   separate, already-existing, already-individually-authorized step
   (`authorize_and_run_task`) -- this module does not prematurely wire
   background execution, per WP-104's own explicit instruction.

`RouteKind.UNKNOWN` (from either stage) never reaches any of the
above -- :func:`authorize_and_route` returns a `RouteOutcome` with no
`decision` at all in that case, since nothing was authorized.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.adapters.reasoning.local import LocalReasoningAdapter
from jarvis.application.routing.router import RouteKind, RouteResult, RoutingError, generate_route
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.domain.transcript import Transcript
from jarvis.kernel.capabilities import build_default_registry
from jarvis.kernel.capability_dispatch import PLAN_STEP_EXECUTORS
from jarvis.kernel.intent import AmbiguousJobSearchSite, UnrecognizedIntent, resolve_intent
from jarvis.kernel.tasks import authorize_and_create_task

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.policy import Decision
    from jarvis.ports.clock import ClockPort
    from jarvis.ports.embedding import EmbeddingPort
    from jarvis.ports.identifier import IdPort
    from jarvis.ports.reasoning import ReasoningPort

_logger = logging.getLogger(__name__)

_DETERMINISTIC_ROUTE_CONFIDENCE = 1.0
"""A real, fixed, informational-only confidence for every Stage-A route -- it matched a
fixed grammar exactly, not a probabilistic guess. Never consulted by any authorization
decision, mirroring `application/routing/router.py`'s own identical reasoning for Stage B."""

_FILLER_PREFIXES = ("please ", "can you ", "could you ", "would you ")
"""A small, fixed, bounded set -- WP-104's own named examples only ("please"/"can you"),
not a general NLP grammar. At most one prefix is stripped per call (see
:func:`_normalize_for_deterministic_routing`)."""

_FILLER_SUFFIX_CHARS = ".?!"
"""Trailing punctuation stripped after any filler prefix -- covers "can you open youtube?"."""


def _normalize_for_deterministic_routing(text: str) -> str:
    """Strip a small, fixed set of conversational filler words/punctuation, case-insensitively.

    Only the recognized filler is removed -- the remaining text's own
    original casing is preserved untouched, since some commands (e.g.
    "read <path>") are themselves case-sensitive in their argument,
    even though the command keyword itself is matched
    case-insensitively by `resolve_intent()`.
    """
    normalized = text.strip()
    lowered = normalized.lower()
    for prefix in _FILLER_PREFIXES:
        if lowered.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
            break
    while normalized and normalized[-1] in _FILLER_SUFFIX_CHARS:
        normalized = normalized[:-1].strip()
    return normalized


def route_deterministically(text: str) -> RouteResult:
    """Stage A: resolve `text` via `resolve_intent()`, after a small, bounded normalization pass.

    Never raises, never guesses -- returns `RouteKind.UNKNOWN` for
    anything `resolve_intent()` itself does not confidently recognize,
    exactly mirroring `resolve_intent()`'s own "never guess" contract.
    A thin, public wrapper over :func:`_route_deterministically`, which
    additionally tells :func:`authorize_and_route` whether this
    particular `UNKNOWN` is worth escalating to Stage B at all --
    discarded here since this function's own callers (tests, anything
    inspecting Stage A in isolation) only need the route itself.
    """
    return _route_deterministically(text)[0]


def _route_deterministically(text: str) -> tuple[RouteResult, bool]:
    """The real Stage A implementation: `(route, should_escalate_to_reasoning)`.

    **Why a second return value, not just `RouteKind.UNKNOWN` for
    both real cases `resolve_intent()` can produce**: `UnrecognizedIntent`
    and `AmbiguousJobSearchSite` are genuinely different situations.
    The former means Stage A has no idea what this is -- escalating to
    reasoning is the right move. The latter means Stage A already
    recognizes *exactly* what this is (a job search) and exactly
    what's missing (a site clause) -- `kernel/intent.py`'s own
    docstring calls this out specifically so a caller (there,
    `kernel/voice_loop.py`) can "speak a real, specific clarifying
    question rather than either guessing or the generic 'I didn't
    understand that'". Falling through to Stage B here would silently
    discard that already-known, more-precise answer in favor of a
    reasoning call that has strictly less information than Stage A
    already does -- a real, avoidable quality regression, not a
    hypothetical one (caught live while writing this module's own
    tests). So `AmbiguousJobSearchSite` returns `UNKNOWN` but never
    escalates; `UnrecognizedIntent` does.
    """
    normalized = _normalize_for_deterministic_routing(text)
    resolved = resolve_intent(Transcript(text=normalized))

    if isinstance(resolved, UnrecognizedIntent):
        return (
            RouteResult(
                kind=RouteKind.UNKNOWN,
                original_input=text,
                confidence=0.0,
                source="deterministic",
                detail="No known deterministic command matched this request.",
            ),
            True,
        )
    if isinstance(resolved, AmbiguousJobSearchSite):
        return (
            RouteResult(
                kind=RouteKind.UNKNOWN,
                original_input=text,
                confidence=0.0,
                source="deterministic",
                detail=(
                    f"Recognized a job-search request for {resolved.keywords!r}, but no "
                    "linkedin/indeed site was given -- please specify one."
                ),
            ),
            False,
        )
    return (
        RouteResult(
            kind=RouteKind.DETERMINISTIC_COMMAND,
            original_input=text,
            confidence=_DETERMINISTIC_ROUTE_CONFIDENCE,
            source="deterministic",
            capability_id=resolved.capability_id,
            arguments=resolved.arguments,
        ),
        False,
    )


@dataclass(frozen=True)
class RouteOutcome:
    """The result of one authorize_and_route() call -- what `jarvis do` needs to print.

    Attributes:
        route: The real `RouteResult` Stage A (or Stage B, if Stage A
            returned `RouteKind.UNKNOWN`) produced.
        decision: The real `Decision` from downstream authorization,
            if this route caused one -- executing a deterministic
            command via `PLAN_STEP_EXECUTORS`, or creating a task for
            a complex goal. `None` if no downstream authorization was
            attempted at all (`RouteKind.UNKNOWN`, or a
            `DETERMINISTIC_COMMAND` naming a real capability with no
            entry in `PLAN_STEP_EXECUTORS` -- see module docstring).
        execution_result: The wrapped `authorize_and_*` function's own
            full return value, if a deterministic command was actually
            executed. `None` otherwise.
        task_id: The new task's real, stable identifier, if a
            `COMPLEX_GOAL` route created one and that creation was
            granted. `None` otherwise.
    """

    route: RouteResult
    decision: Decision | None
    execution_result: object | None
    task_id: str | None


async def authorize_and_route(  # noqa: PLR0913 -- one per composition-function pass-through
    text: str,
    provider: ReasoningPort | None = None,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None = None,
    embedding_port: EmbeddingPort | None = None,
    clock: ClockPort | None = None,
    id_port: IdPort | None = None,
) -> RouteOutcome:
    """Route `text` (Stage A, then Stage B if needed), then act only within the real boundary.

    See module docstring for the exact, narrow set of real actions
    this can ever cause -- executing one of four pre-wired,
    `Tier.ALLOW` capabilities, or creating (never running) a task.
    Every other route (`RouteKind.UNKNOWN`, or a real capability with
    no wired executor) causes no authorization attempt at all.

    **Never raises `RoutingError`** -- a real, deliberate departure
    from `authorize_and_run_plan`'s own treatment of a malformed
    `PlanningError`. A malformed Stage-B response is a genuinely
    different situation from a malformed plan: `plan run`/`task run`
    are explicit, user-invoked planning actions where surfacing a real
    failure is the correct, actionable behavior, but `jarvis do`'s own
    reasoning fallback is exactly the case WP-104's own requirement
    names directly ("reasoning failure handled safely" -- do not
    silently execute a guess, but also do not crash): a
    `RoutingError` here is caught and converted into a real
    `RouteKind.UNKNOWN` result instead, the same outcome an
    unrecognized deterministic command already produces.
    """
    route, should_escalate = _route_deterministically(text)

    if should_escalate:
        registry = build_default_registry()
        if provider is None:
            _logger.warning(
                "router: no cloud reasoning provider was supplied -- falling back to the "
                "local model for the reasoning fallback. See kernel/planning.py's own, "
                "identical warning for the real, measured local-model reliability gap this "
                "shares. Pass an explicit, real cloud-backed ReasoningPort to avoid this."
            )
        real_provider = provider or LocalReasoningAdapter()
        try:
            route = await generate_route(
                Tainted(text, Provenance.user()),
                real_provider,
                lambda capability_id: capability_id in registry,
            )
        except RoutingError as exc:
            _logger.debug("router: reasoning fallback failed, reporting UNKNOWN: %s", exc)
            route = RouteResult(
                kind=RouteKind.UNKNOWN,
                original_input=text,
                confidence=0.0,
                source="reasoning",
                detail=f"The reasoning fallback failed: {exc}",
            )

    if (
        route.kind == RouteKind.DETERMINISTIC_COMMAND
        and route.capability_id is not None
        and route.capability_id in PLAN_STEP_EXECUTORS
    ):
        executor = PLAN_STEP_EXECUTORS[route.capability_id]
        arguments = route.arguments.value if route.arguments is not None else {}
        outcome = executor(
            arguments, physical_confirmation_available, remote_confirmation_available, chain_path
        )
        return RouteOutcome(
            route=route, decision=outcome.decision, execution_result=outcome.result, task_id=None
        )

    if route.kind == RouteKind.COMPLEX_GOAL and route.goal is not None:
        create_outcome = authorize_and_create_task(
            route.goal,
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=chain_path,
            database_path=database_path,
            embedding_port=embedding_port,
            clock=clock,
            id_port=id_port,
        )
        return RouteOutcome(
            route=route,
            decision=create_outcome.decision,
            execution_result=None,
            task_id=create_outcome.task_id,
        )

    return RouteOutcome(route=route, decision=None, execution_result=None, task_id=None)
