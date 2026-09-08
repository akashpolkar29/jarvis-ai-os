"""project.start / project.status: a typed-goal workflow on top of planning.run_plan.

**Not a new planning/execution engine.** ``authorize_and_start_project``
is a thin composition wrapping the already-real, already-Accepted
``planning.run_plan`` (``kernel/planning.py``, ADR-0062) unmodified,
plus a real, structured-content status record layered directly on top
of the already-real, already-Accepted ``memory.write``/
``memory.retrieve`` capabilities -- mirroring
``jarvis.kernel.job_application``'s own "structured value on top of
unmodified memory" convention exactly, not a second ledger mechanism.

**Effect/Tier**: ``authorize_and_start_project`` reuses
``authorize_and_run_plan``'s own outer-gate classification exactly --
``Effect.EXECUTE``/``Tier.CONFIRM`` (``PLANNING_RUN_PLAN_CAPABILITY_ID``).
There is no separate classification logic here for the outer gate.
The status record it writes on a granted, attempted plan reuses
``authorize_and_remember``'s own ``Effect.WRITE_LOCAL``/``Tier.CONFIRM``
(ADR-0049, ``Classification.PUBLIC`` -- a project goal string and its
own stuck reason are not data this project's privacy model treats as
SECRET). ``authorize_and_get_project_status`` reuses
``authorize_and_recall``'s own ``Effect.READ_LOCAL``/``Tier.ALLOW``.

**This must never become a second authorization path.** Nothing here
changes what ``planning.run_plan`` itself authorizes or how -- every
real plan step still goes through its own, individual
``authorize_by_id()`` call via ``execute_plan()``, exactly as ADR-0062
requires; this module only ever reads the outer gate's/each step's own
already-computed ``Decision``, never grants anything itself, and the
one new write this module performs (the status record) goes through
its own real, unmodified ``memory.write`` authorization like any other
memory write.

**A real, load-bearing finding from investigating before building,
worth stating precisely rather than smoothing over**: the working
prompt that requested this module assumed "stuck" already meant *"a
Tier.CONFIRM step blocks mid-plan awaiting the user."* That is not
what the real, current code does. ``application/planning/executor.py``
restricts ``planning.run_plan`` to **Tier.ALLOW-only** steps
(narrower than ADR-0062's own stated Tier.CONFIRM ceiling, a
deliberate v1 restriction -- see that module's own docstring); any
step above ``Tier.ALLOW`` fails ``_validate_plan()`` and raises
``PlanValidationError`` for the **whole plan, before any step runs**
-- it does not pause a single step for confirmation. Combined with
``Tier.ALLOW`` being unconditionally granted (``domain/policy.py``),
no step in a plan that ever passes validation can currently be denied
either. So the real, reachable "stuck" signals today are:

1. ``PlanningError`` (``application/planning/planner.py``) -- the
   provider's proposed plan failed structural validation (malformed
   JSON, or it named a capability that isn't registered at all).
   Raised only if the outer gate was granted; **this module catches
   it, writes a real "stuck" status record with the exception's own
   message as the reason, then re-raises unchanged** -- ``jarvis
   project start`` fails exactly like ``jarvis plan run`` already does
   for this same exception (``cli/main.py``'s own existing broad
   except tuple already names both ``PlanningError``/
   ``PlanValidationError``), with the added, real side effect that the
   reason is now durably recorded for a later ``jarvis project
   status`` to retrieve.
2. ``PlanValidationError`` (``application/planning/executor.py``) --
   the plan was structurally valid but named a capability with no
   registered plan-step executor, or one above the Tier.ALLOW ceiling.
   Handled identically to (1).
3. ``PlanExecutionResult.aborted is True`` -- a real, defined
   ``execute_plan()`` outcome for "a step was denied," **not currently
   reachable** given every real ``PLAN_STEP_EXECUTORS`` entry is
   Tier.ALLOW and Tier.ALLOW always grants. Read defensively anyway
   (ignoring a real field on a value already in hand would be worse
   than checking it) and reported as a returned, not raised, "stuck"
   state -- matching this codebase's own consistent "denial is a
   returned ``Decision.granted=False``, never an exception" convention
   everywhere else, unlike (1)/(2) which are genuine errors. No new
   test forces this path: doing so would require registering a
   non-Tier.ALLOW capability as a plan-step executor, which is exactly
   the kind of change this module must not make (see ADR-0062/the
   executor's own Tier.ALLOW-only ceiling, both explicitly out of this
   module's scope to loosen). Proven instead by a pure, direct unit
   test against :func:`_state_for_result` alone, no registry involved.

A denied **outer** gate (``planning.run_plan`` itself not authorized,
e.g. no confirmation available) is a fourth, distinct case, already
correctly handled by ``authorize_and_run_plan`` itself
(``result is None``) -- nothing was attempted, so nothing is recorded;
this module does not write a status record for that case, matching
the "denial means nothing happened, nothing to record" reasoning
applied consistently above. No retry or replan is attempted anywhere
in this module, matching
``docs/architecture/planning-retry-replan-scoping-notes.md``'s own
2026-09-07 decision (already accepted, not re-decided here): a stuck
plan simply ends there, honestly reporting why.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.adapters.clock import SystemClockAdapter
from jarvis.application.planning.executor import PlanValidationError
from jarvis.application.planning.planner import PlanningError
from jarvis.kernel.memory import authorize_and_recall, authorize_and_remember
from jarvis.kernel.planning import authorize_and_run_plan

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.application.planning.executor import PlanExecutionResult
    from jarvis.domain.memory import MemoryRecord
    from jarvis.domain.policy import Decision
    from jarvis.ports.clock import ClockPort
    from jarvis.ports.embedding import EmbeddingPort
    from jarvis.ports.identifier import IdPort
    from jarvis.ports.reasoning import ReasoningPort

_PROJECT_GOAL_KIND = "project_goal"
"""The real, fixed marker value stored under each record's own "kind" key,
mirroring ``jarvis.kernel.job_application``'s own identical convention."""

VALID_PROJECT_STATES = ("completed", "stuck")
"""The real, fixed state vocabulary this module ever writes -- see the
module docstring for exactly which real code paths produce each one."""

_LIST_QUERY = "project goal state reason plan status stuck completed"
"""A fixed query text chosen to score highly against any project-goal
record's own embedded JSON (whose keys/values are close to these exact
words), mirroring ``job_application.py``'s own identical convention."""

_RECALL_LIST_LIMIT = 1000
"""A generous, fixed top-K passed to the underlying memory.retrieve call --
see ``job_application.py``'s own docstring for the real, honest limitation
this implies, unchanged here."""


def _state_for_result(result: PlanExecutionResult) -> tuple[str, str | None]:
    """Derive (state, reason) from a granted, attempted plan's own real result.

    A pure function, deliberately: exercised directly by a unit test
    against a hand-constructed ``PlanExecutionResult``, with no real
    registry/orchestrator involved -- see the module docstring's own
    point 3 for why ``aborted is True`` cannot be reached any other
    way today.
    """
    if not result.aborted:
        return "completed", None
    last = result.step_records[-1]
    reason = (
        f"Plan step {last.step.capability_id.value!r} was denied "
        f"(reasons={last.decision.reasons!r})."
    )
    return "stuck", reason


def _record_project_goal_state(  # noqa: PLR0913 -- one per composition-function pass-through
    goal: str,
    state: str,
    reason: str | None,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None,
    embedding_port: EmbeddingPort | None,
    clock: ClockPort | None,
    id_port: IdPort | None,
) -> str | None:
    """Write one real project-goal status record. Reuses authorize_and_remember unmodified.

    Returns:
        The real, granted record's own identifier, or ``None`` if the
        underlying ``memory.write`` call was itself denied (a real,
        checked outcome, never assumed).
    """
    resolved_clock = clock or SystemClockAdapter()
    record: dict[str, object] = {
        "kind": _PROJECT_GOAL_KIND,
        "goal": goal,
        "state": state,
        "reason": reason,
        "recorded_at": resolved_clock.now().isoformat(),
    }
    write_outcome = authorize_and_remember(
        record,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=resolved_clock,
        id_port=id_port,
    )
    return write_outcome.identifier if write_outcome.decision.granted else None


@dataclass(frozen=True)
class ProjectStartOutcome:
    """The result of one authorize_and_start_project() call.

    Attributes:
        decision: The ``planning.run_plan`` outer gate's own real
            ``Decision``. If not granted, nothing else in this outcome
            is meaningful -- the planner never ran at all, matching
            ``authorize_and_run_plan``'s own established contract.
        state: ``"completed"`` or ``"stuck"`` if the outer gate was
            granted and the planner was attempted and returned
            normally; ``None`` if the outer gate was denied (nothing
            was attempted). A ``PlanningError``/``PlanValidationError``
            never reaches this field -- see the module docstring for
            why those two real failure modes raise instead.
        reason: The real, human-readable reason the plan is stuck, if
            ``state == "stuck"``; ``None`` otherwise.
        record_identifier: The real project-goal ``MemoryRecord``'s
            own identifier, if a status record was successfully
            written; ``None`` if nothing was attempted (``state`` is
            ``None``) or the status write itself was denied.
    """

    decision: Decision
    state: str | None
    reason: str | None
    record_identifier: str | None


async def authorize_and_start_project(  # noqa: PLR0913 -- one per composition-function pass-through
    goal: str,
    provider: ReasoningPort | None = None,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None = None,
    embedding_port: EmbeddingPort | None = None,
    clock: ClockPort | None = None,
    id_port: IdPort | None = None,
) -> ProjectStartOutcome:
    """Wire up planning.run_plan for `goal`, then record a real, durable status.

    See the module docstring for the exact real, current meaning of
    "stuck" this function reuses -- not the mid-plan-confirmation
    signal a stale premise assumed, since that signal cannot occur
    given today's Tier.ALLOW-only planner ceiling.

    Args:
        goal: The real, natural-language project goal, typed directly
            by the user -- passed straight through to
            ``authorize_and_run_plan``, wrapped there exactly as every
            other directly-typed argument in this codebase already is.
        provider: As ``authorize_and_run_plan``'s own identical
            parameter -- defaults to the same real, local-only
            ``LocalReasoningAdapter``, with the same real, honest
            reliability warning on that default's own known ~33
            percent failure rate.
        physical_confirmation_available: Passed straight through to
            both the outer gate and, if reached, the status-record
            write.
        remote_confirmation_available: As above.
        chain_path: Where every real decision this call makes lands --
            the outer gate's, every real plan step's, and the status
            record's own ``memory.write``, all in this same file.
        database_path: Where the real memory store lives. Overridable
            for tests.
        embedding_port: Overridable for tests -- important to
            override, in fact: a granted status write with no override
            triggers a real model download on first use.
        clock: Defaults to a real ``SystemClockAdapter``.
        id_port: Defaults to a real ``UuidIdAdapter``.

    Returns:
        A ``ProjectStartOutcome`` -- see its own docstring. Never
        returned at all if ``PlanningError``/``PlanValidationError``
        was raised (see below).

    Raises:
        jarvis.application.planning.planner.PlanningError: If the
            provider's proposed plan fails real, structural validation.
            A real "stuck" status record is written, with this
            exception's own message as the reason, *before* this
            propagates -- the caller still sees the same real
            exception ``jarvis plan run`` already surfaces identically.
        jarvis.application.planning.executor.PlanValidationError: If a
            structurally-valid plan names a capability with no
            registered executor, or one above this planner's
            Tier.ALLOW-only ceiling. Handled identically to
            ``PlanningError`` above.
    """
    try:
        decision, result = await authorize_and_run_plan(
            goal,
            provider,
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=chain_path,
        )
    except (PlanningError, PlanValidationError) as exc:
        _record_project_goal_state(
            goal,
            "stuck",
            f"{type(exc).__name__}: {exc}",
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=chain_path,
            database_path=database_path,
            embedding_port=embedding_port,
            clock=clock,
            id_port=id_port,
        )
        raise

    if not decision.granted or result is None:
        return ProjectStartOutcome(
            decision=decision, state=None, reason=None, record_identifier=None
        )

    state, reason = _state_for_result(result)
    record_identifier = _record_project_goal_state(
        goal,
        state,
        reason,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=clock,
        id_port=id_port,
    )
    return ProjectStartOutcome(
        decision=decision, state=state, reason=reason, record_identifier=record_identifier
    )


@dataclass(frozen=True)
class ProjectStatusOutcome:
    """The result of one authorize_and_get_project_status() call.

    Attributes:
        decision: The ``Decision`` for the underlying ``memory.retrieve``
            call this reuses -- always granted (``Tier.ALLOW``),
            matching ``JobApplicationListOutcome``'s own "explicit
            check, not asserted away" convention.
        record: The most recent real project-goal ``MemoryRecord``
            whose own ``goal`` field exactly matches the queried goal,
            or ``None`` if no such record exists yet. Read a record's
            own ``state``/``reason``/``recorded_at`` fields directly
            from ``record.value.value`` (a plain ``dict``), mirroring
            ``JobApplicationListOutcome``'s own identical shape.
    """

    decision: Decision
    record: MemoryRecord | None


def authorize_and_get_project_status(  # noqa: PLR0913 -- one per composition-function pass-through
    goal: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None = None,
    embedding_port: EmbeddingPort | None = None,
    clock: ClockPort | None = None,
    id_port: IdPort | None = None,
) -> ProjectStatusOutcome:
    """Retrieve the most recent real status record for `goal`. Reuses authorize_and_recall.

    See the module docstring for the real, honest broad-recall-then-
    filter approximation this shares with ``job_application.list`` --
    the same real limitation, not a new one.

    Args:
        goal: The exact, real goal string to look up -- must match a
            prior ``authorize_and_start_project`` call's own ``goal``
            argument exactly (plain string equality, no fuzzy match).
        physical_confirmation_available: Passed straight through to
            ``authorize_and_recall``.
        remote_confirmation_available: As above.
        chain_path: Where the audit chain is persisted.
        database_path: Where the real memory store lives. Overridable
            for tests.
        embedding_port: Overridable for tests.
        clock: Defaults to a real ``SystemClockAdapter``.
        id_port: Defaults to a real ``UuidIdAdapter``. Unused by a
            read, threaded through only for ``authorize_and_recall``'s
            own shared helper.

    Returns:
        A ``ProjectStatusOutcome`` -- see its own docstring.
    """
    recall_outcome = authorize_and_recall(
        _LIST_QUERY,
        limit=_RECALL_LIST_LIMIT,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=clock,
        id_port=id_port,
    )
    matching = [
        record
        for record in recall_outcome.records
        if isinstance(record.value.value, dict)
        and record.value.value.get("kind") == _PROJECT_GOAL_KIND
        and record.value.value.get("goal") == goal
    ]
    latest = max(matching, key=lambda record: record.written_at) if matching else None
    return ProjectStatusOutcome(decision=recall_outcome.decision, record=latest)
