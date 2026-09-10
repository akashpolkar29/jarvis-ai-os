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

**WP-111 (2026-09-10)**: an optional `event_bus` parameter is passed
straight through, unmodified, to `authorize_and_create_task` -- a real
`TaskCreated` event (`jarvis.domain.events`) is published the moment a
`COMPLEX_GOAL` route actually creates a task, if a real, shared bus
was supplied. This router itself never runs a task (see above), so no
real `TaskStatusChanged` event can ever originate from this function
today -- only `kernel.tasks.authorize_and_run_task` (a separate,
explicit call, e.g. `jarvis task run`) can produce one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from jarvis.adapters.clock import SystemClockAdapter
from jarvis.adapters.reasoning.local import LocalReasoningAdapter
from jarvis.application.routing.router import RouteKind, RouteResult, RoutingError, generate_route
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.domain.transcript import Transcript
from jarvis.kernel.capabilities import (
    CALENDAR_LIST_EVENTS_CAPABILITY_ID,
    EMAIL_LIST_MESSAGES_CAPABILITY_ID,
    EMAIL_READ_MESSAGE_CAPABILITY_ID,
    build_default_registry,
)
from jarvis.kernel.capability_dispatch import (
    DEFAULT_EMAIL_FOLDER,
    DEFAULT_EMAIL_LIST_LIMIT,
    PLAN_STEP_EXECUTORS,
    CalendarListStepResult,
    EmailListStepResult,
    EmailReadStepResult,
)
from jarvis.kernel.communications import (
    authorize_and_list_calendar_events,
    authorize_and_list_email,
    authorize_and_read_email,
)
from jarvis.kernel.intent import (
    AmbiguousJobSearchSite,
    ResolvedIntent,
    UnrecognizedIntent,
    resolve_intent,
)
from jarvis.kernel.tasks import authorize_and_create_task

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from jarvis.domain.events import EventBus
    from jarvis.domain.policy import Decision
    from jarvis.ports.calendar import CalendarPort
    from jarvis.ports.clock import ClockPort
    from jarvis.ports.email import EmailPort
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


_EMAIL_LIST_PHRASES = (
    "list emails",
    "recent emails",
    "show my emails",
    "show my recent emails",
    "show recent emails",
)
"""A small, fixed, exact-match set (WP-114) -- mirrors `resolve_intent()`'s own
"recent files"-shaped zero-argument commands, not a general NLP grammar. Deliberately
exact-match, not substring/prefix: these are short enough that requiring the whole
normalized text to match keeps this unambiguous (Step 14's own explicit requirement)."""

_READ_EMAIL_COMMAND = "read email"
"""Mirrors `resolve_intent()`'s own "read <path>"/"recall <query>" shape exactly --
everything after this fixed prefix, verbatim, is the real message id. A real, honest
limitation, not hidden: this requires a literal message id recited, not "the latest
email" or any other relative reference -- the backend (`EmailPort.read_message`) has no
"latest"/"by sender" lookup primitive, and Step 3's own instruction is explicit: do not
invent one. Deliberately matched as a bare two-word command too (with no trailing id)
-- see `_resolve_communications_command`'s own docstring for why that case is terminal
UNKNOWN, not a silent fall-through to `resolve_intent()`'s own colliding "read <path>"."""

_CALENDAR_TRIGGER_PHRASES = (
    "what's on my calendar",
    "whats on my calendar",
    "show my calendar",
    "what meetings do i have",
    "calendar",
)
"""Longest/most-specific phrasings first, purely for readability -- `startswith` makes
the actual match order-independent, since no phrase here is a prefix of another's own
non-matching remainder. Covers Step 4's three named examples ("what's on my calendar
today?", "show my calendar for tomorrow", "what meetings do I have this week?") plus
the bare "calendar"/no-date-word case, which defaults to today (see
`_CALENDAR_RANGE_SUFFIXES`)."""

_CALENDAR_RANGE_SUFFIXES: dict[str, str] = {
    "": "today",
    "today": "today",
    "for today": "today",
    "tomorrow": "tomorrow",
    "for tomorrow": "tomorrow",
    "this week": "this_week",
    "for this week": "this_week",
}
"""Maps the real, literal text remaining after a `_CALENDAR_TRIGGER_PHRASES` match to one
of exactly three real range keywords. Deliberately small and exact -- not a general date
parser; "next monday"/"in 3 days" and similar remain genuinely unsupported, reported
honestly as UNKNOWN rather than guessed (Step 14's own explicit requirement)."""


def _calendar_range_bounds(range_keyword: str, now: datetime) -> tuple[datetime, datetime]:
    """Compute `[start, end)` for one of the three real range keywords, from a real `now`.

    "today"/"tomorrow" are a real, midnight-to-midnight UTC day (`now`
    is already UTC -- `ClockPort.now()`'s own contract). "this_week" is
    Monday 00:00 UTC through the following Monday 00:00 UTC, the
    common Monday-Sunday convention -- a real, named choice, not the
    only reasonable one, but a single, fixed, deterministic rule
    (never ambiguous, matching Step 14's own requirement).
    """
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_keyword == "today":
        return start_of_today, start_of_today + timedelta(days=1)
    if range_keyword == "tomorrow":
        start = start_of_today + timedelta(days=1)
        return start, start + timedelta(days=1)
    monday = start_of_today - timedelta(days=start_of_today.weekday())
    return monday, monday + timedelta(days=7)


def _resolve_communications_command(
    text: str, clock: ClockPort
) -> ResolvedIntent | UnrecognizedIntent | None:
    """Typed-router-only grammar for email list/read + calendar list-events.

    Returns `None` if `text` matches none of this function's own
    trigger phrases at all -- the caller should try
    `kernel.intent.resolve_intent()` next. Returns `UnrecognizedIntent`
    (never `None`) if a trigger phrase *did* match but the remaining
    text is not one this function can resolve (e.g. "read email" with
    no id, or "calendar next monday") -- **deliberately terminal, not
    a fall-through**: `resolve_intent()`'s own pre-existing single-word
    "read <path>" command would otherwise happily (mis)resolve "read
    email" to `fs.read_file` with `path="email"`, a real collision
    caught empirically (not assumed) while first writing this
    function's own tests. Mirrors `AmbiguousJobSearchSite`'s identical
    reasoning for not escalating to Stage B either: once a trigger
    phrase is recognized, Stage A already has a more precise read on
    what's missing/wrong than a reasoning call would.

    **Deliberately NOT added to `kernel.intent.resolve_intent()`**,
    the shared grammar both this router and `kernel.voice_loop` call --
    two real, independent reasons, stated plainly, matching that
    module's own docstring's already-established reasoning for why
    these three commands had no voice grammar at all before this work
    package:

    1. `communications.list_email`/`read_email`/`list_calendar_events`
       need a real, pre-configured `email_port`/`calendar_port` with
       no safe default -- adding this to the shared, pure
       `resolve_intent()` would make it resolvable via voice too,
       where `kernel.voice_loop._authorize_and_execute`'s own dispatch
       has no branch for these three capability ids and would fall
       through to its final, unguarded music-command dict lookup,
       raising a real `KeyError` for a newly-resolvable voice phrase --
       a real, avoidable regression this work package's own hard
       boundary ("do not implement voice... do not touch voice
       runtime") requires avoiding, not introducing.
    2. "calendar today"/"tomorrow"/"this week" needs the real, current
       wall-clock time (`ClockPort`) to resolve to a concrete ISO-8601
       range -- `resolve_intent()` is a deliberately pure, clockless
       function (see its own module docstring); threading a `ClockPort`
       through it would be a real, invasive signature change rippling
       into every caller, including `kernel.voice_loop`, which this
       work package's own hard boundary also forbids touching.

    Confined entirely to `kernel.router` (never imported by
    `kernel.voice_loop`), this function cannot affect voice in any way
    -- proven structurally, not just by convention.
    """
    lowered = text.lower()
    if lowered in _EMAIL_LIST_PHRASES:
        return ResolvedIntent(
            capability_id=EMAIL_LIST_MESSAGES_CAPABILITY_ID,
            arguments=Tainted(
                {"folder": DEFAULT_EMAIL_FOLDER, "limit": DEFAULT_EMAIL_LIST_LIMIT},
                Provenance.user(),
            ),
        )
    if lowered == _READ_EMAIL_COMMAND or lowered.startswith(_READ_EMAIL_COMMAND + " "):
        message_id = text[len(_READ_EMAIL_COMMAND) :].strip()
        if not message_id:
            return UnrecognizedIntent()
        return ResolvedIntent(
            capability_id=EMAIL_READ_MESSAGE_CAPABILITY_ID,
            arguments=Tainted({"message_id": message_id}, Provenance.user()),
        )

    for trigger in _CALENDAR_TRIGGER_PHRASES:
        if not lowered.startswith(trigger):
            continue
        rest = lowered[len(trigger) :].strip()
        range_keyword = _CALENDAR_RANGE_SUFFIXES.get(rest)
        if range_keyword is None:
            return UnrecognizedIntent()
        start, end = _calendar_range_bounds(range_keyword, clock.now())
        return ResolvedIntent(
            capability_id=CALENDAR_LIST_EVENTS_CAPABILITY_ID,
            arguments=Tainted(
                {"start": start.isoformat(), "end": end.isoformat()}, Provenance.user()
            ),
        )
    return None


def route_deterministically(text: str, *, clock: ClockPort | None = None) -> RouteResult:
    """Stage A: resolve `text` via `resolve_intent()`, after a small, bounded normalization pass.

    Never raises, never guesses -- returns `RouteKind.UNKNOWN` for
    anything neither `resolve_intent()` nor this module's own
    communications-command grammar (see
    :func:`_resolve_communications_command`) confidently recognizes. A
    thin, public wrapper over :func:`_route_deterministically`, which
    additionally tells :func:`authorize_and_route` whether this
    particular `UNKNOWN` is worth escalating to Stage B at all --
    discarded here since this function's own callers (tests, anything
    inspecting Stage A in isolation) only need the route itself.

    Args:
        text: The real, typed text to route.
        clock: Needed only for a "calendar today/tomorrow/this week"
            match (see :func:`_resolve_communications_command`).
            Defaults to a real `SystemClockAdapter`. Overridable for
            tests that need a fixed "now".
    """
    return _route_deterministically(text, clock or SystemClockAdapter())[0]


def _route_deterministically(text: str, clock: ClockPort) -> tuple[RouteResult, bool]:
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

    **WP-114**: :func:`_resolve_communications_command`, this module's
    own, separate, typed-router-only grammar for "list emails"/
    "read email <id>"/"calendar today|tomorrow|this week" (see that
    function's own docstring for why these three live here, not in
    `kernel.intent.resolve_intent()`, the shared grammar voice also
    calls), is tried **first**, before `resolve_intent()` -- not as a
    fallback for its `UnrecognizedIntent`. A real, empirically-caught
    collision forced this ordering, not a style preference:
    `resolve_intent()`'s own pre-existing single-word "read <path>"
    command happily resolves "read email <id>" to `fs.read_file` with
    `path="email <id>"` -- it is never `UnrecognizedIntent`, so a
    fallback-only check would never even run for this exact phrase.
    Checking the new grammar first avoids this cleanly; it introduces
    no new collision of its own, since every phrase in
    :func:`_resolve_communications_command` starts with a word
    (`"list"`/`"recent"`/`"show"`/`"what's"`/`"what meetings"`/
    `"calendar"`) that matches none of `resolve_intent()`'s own
    existing single- or two-word command keywords.
    """
    normalized = _normalize_for_deterministic_routing(text)
    communications_resolved = _resolve_communications_command(normalized, clock)
    if isinstance(communications_resolved, ResolvedIntent):
        return (
            RouteResult(
                kind=RouteKind.DETERMINISTIC_COMMAND,
                original_input=text,
                confidence=_DETERMINISTIC_ROUTE_CONFIDENCE,
                source="deterministic",
                capability_id=communications_resolved.capability_id,
                arguments=communications_resolved.arguments,
            ),
            False,
        )
    if isinstance(communications_resolved, UnrecognizedIntent):
        return (
            RouteResult(
                kind=RouteKind.UNKNOWN,
                original_input=text,
                confidence=0.0,
                source="deterministic",
                detail=(
                    "Recognized this as an email/calendar command, but could not determine "
                    "the rest (e.g. a missing message id, or an unsupported date phrase)."
                ),
            ),
            False,
        )

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
    event_bus: EventBus | None = None,
    email_port: EmailPort | None = None,
    calendar_port: CalendarPort | None = None,
) -> RouteOutcome:
    """Route `text` (Stage A, then Stage B if needed), then act only within the real boundary.

    See module docstring for the exact, narrow set of real actions
    this can ever cause -- executing one of the pre-wired,
    `Tier.ALLOW` capabilities in `PLAN_STEP_EXECUTORS`, directly
    `await`-ing one of the three `communications.*` reads (WP-114, only
    when the matching port was supplied to this specific call -- see
    below), or creating (never running) a task. Every other route
    (`RouteKind.UNKNOWN`, or a real capability with no wired executor
    and no configured port) causes no authorization attempt at all.

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

    `email_port`/`calendar_port` (WP-114) are the real, already-
    constructed ports a real caller (e.g. `jarvis ui`) supplies when
    email/calendar are configured on this device -- `None` (the
    default) means a `communications.list_email`/`read_email`/
    `list_calendar_events` route is recognized but never executed, the
    same honest, structural "recognized, not wired" outcome a real but
    unwired capability from Stage B already produces (module
    docstring). **Never constructed here** -- `kernel` may not import a
    concrete `EmailPort`/`CalendarPort` adapter (only `cli` may,
    matching `jarvis send-email`'s/`jarvis email list`'s own, identical
    precedent).
    """
    real_clock = clock or SystemClockAdapter()
    route, should_escalate = _route_deterministically(text, real_clock)

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

    if (
        route.kind == RouteKind.DETERMINISTIC_COMMAND
        and route.capability_id == EMAIL_LIST_MESSAGES_CAPABILITY_ID
        and email_port is not None
    ):
        arguments = route.arguments.value if route.arguments is not None else {}
        raw_limit = arguments.get("limit", DEFAULT_EMAIL_LIST_LIMIT)
        limit = raw_limit if isinstance(raw_limit, int) else int(str(raw_limit))
        decision, summaries = await authorize_and_list_email(
            str(arguments.get("folder", DEFAULT_EMAIL_FOLDER)),
            limit,
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=chain_path,
            email_port=email_port,
        )
        return RouteOutcome(
            route=route,
            decision=decision,
            execution_result=EmailListStepResult(decision=decision, summaries=summaries),
            task_id=None,
        )

    if (
        route.kind == RouteKind.DETERMINISTIC_COMMAND
        and route.capability_id == EMAIL_READ_MESSAGE_CAPABILITY_ID
        and email_port is not None
    ):
        arguments = route.arguments.value if route.arguments is not None else {}
        decision, message = await authorize_and_read_email(
            str(arguments["message_id"]),
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=chain_path,
            email_port=email_port,
        )
        return RouteOutcome(
            route=route,
            decision=decision,
            execution_result=EmailReadStepResult(decision=decision, message=message),
            task_id=None,
        )

    if (
        route.kind == RouteKind.DETERMINISTIC_COMMAND
        and route.capability_id == CALENDAR_LIST_EVENTS_CAPABILITY_ID
        and calendar_port is not None
    ):
        arguments = route.arguments.value if route.arguments is not None else {}
        decision, events = await authorize_and_list_calendar_events(
            str(arguments["start"]),
            str(arguments["end"]),
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=chain_path,
            calendar_port=calendar_port,
        )
        return RouteOutcome(
            route=route,
            decision=decision,
            execution_result=CalendarListStepResult(decision=decision, events=events),
            task_id=None,
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
            event_bus=event_bus,
        )
        return RouteOutcome(
            route=route,
            decision=create_outcome.decision,
            execution_result=None,
            task_id=create_outcome.task_id,
        )

    return RouteOutcome(route=route, decision=None, execution_result=None, task_id=None)
