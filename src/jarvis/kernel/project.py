"""project.start / project.status: a thin, backward-compatible wrapper over jarvis.kernel.tasks.

**Folded into ``jarvis.kernel.tasks`` (WP-107), by a real, direct user
decision (2026-09-09)**: this module no longer has its own write path
-- it delegates every real write to ``tasks.py``'s own shared helpers
(:func:`~jarvis.kernel.tasks.write_task_record`), sharing the same
``"kind": "task"`` storage marker tasks.py's own new, more general
``authorize_and_create_task``/``authorize_and_run_task`` use, rather
than maintaining a separate, parallel ``"project_goal"`` convention.

**Every real, already-tested, already-live-verified public contract
this module exposes is unchanged**: ``jarvis project start "<goal>"``/
``jarvis project status "<goal>"`` behave byte-for-byte the same as
before this fold -- same ``ProjectStartOutcome``/``ProjectStatusOutcome``
shapes, same ``decision`` semantics (``planning.run_plan``'s own outer
gate, ``Effect.EXECUTE``/``Tier.CONFIRM`` -- never the task-record
write's own gate), same "a denied outer gate writes nothing" rule, same
``state`` vocabulary (``"completed"``/``"stuck"``). This was a real,
deliberate constraint on the fold, not an oversight: changing any of
these would be a real, user-facing breaking change to a capability
that shipped and was live-smoke-tested against a real local model only
days before this fold.

**WP-109 (2026-09-09) closed the real vocabulary seam named above, by
a real, direct user decision ("resolve the stuck vs failed terminology
inconsistency before WP-104")**: investigated first, not assumed --
two of the three real status-producing branches
(`PlanningError`/`PlanValidationError`, and the currently-unreachable
`aborted=True` case) were genuine duplicates of `tasks.py`'s own
identical logic, just spelled differently; a third
(`tasks.authorize_and_run_task`'s own "the outer gate denied after the
task record already existed" branch) has no equivalent here at all,
since this module never writes anything before checking the outer
gate -- that one was left alone, it was never a naming question.

**The real fix**: this module no longer writes its own `"stuck"`
literal to storage at all. It now writes the identical,
canonical `"completed"`/`"failed"` value `tasks.py` itself writes
(`tasks.derive_result_status`, imported directly -- this module's own,
former, near-duplicate `_state_for_result` copy is gone), so
`jarvis task list`/`authorize_and_list_tasks` show one real,
consistent status for this condition regardless of which entry point
created the task -- the real ambiguity is closed.

**What stays `"stuck"`, and why, stated precisely**: this module's own
public `ProjectStartOutcome.state` return value, and `jarvis project
status`'s own printed CLI text, both still say `"stuck"` -- a real,
narrow translation applied only at this module's own return/print
boundary (`_CANONICAL_TO_PROJECT_STATE` below), preserving the exact,
already-shipped, already-tested public contract WP-102 established,
per the user's own explicit instruction not to change
`jarvis project start`/`status`'s semantics unless absolutely
necessary. The one real, explained exception this does *not* paper
over: `ProjectStatusOutcome.record` -- the raw `MemoryRecord` this
module's own `authorize_and_get_project_status` returns -- will now
genuinely contain `status: "failed"` for a project-created failure,
not `"stuck"`. Translating *that* too would mean this module
fabricating a record claiming `"stuck"` was literally persisted when
it was not -- a real, worse problem (an inaccurate record) than the
one being fixed. The CLI's own printed text is translated instead,
exactly where a human actually reads the word, not the raw data
structure a future caller might inspect directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.kernel.memory import authorize_and_recall
from jarvis.kernel.planning import authorize_and_run_plan
from jarvis.kernel.tasks import TASK_KIND, derive_result_status, write_task_record

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.memory import MemoryRecord
    from jarvis.domain.policy import Decision
    from jarvis.ports.clock import ClockPort
    from jarvis.ports.embedding import EmbeddingPort
    from jarvis.ports.identifier import IdPort
    from jarvis.ports.reasoning import ReasoningPort

VALID_PROJECT_STATES = ("completed", "stuck")
"""This module's own, unchanged public vocabulary -- WP-109 (2026-09-09)
translates tasks.py's canonical "completed"/"failed" to this vocabulary
only at this module's own return boundary (see _CANONICAL_TO_PROJECT_STATE);
the stored, canonical value is tasks.py's own, not a second copy of this."""

_LIST_QUERY = "project goal state reason plan status failed completed"
"""WP-109: "failed", not the former "stuck" -- matches the real, canonical
word this module's own writes now actually embed, since a fixed query
string scores against the real stored JSON's own real words."""

_RECALL_LIST_LIMIT = 1000
"""Unchanged by the fold."""

_CANONICAL_TO_PROJECT_STATE = {"completed": "completed", "failed": "stuck"}
"""WP-109's own, one real translation point: tasks.py's canonical,
stored status -> this module's own, unchanged public ``state`` vocabulary.
Applied only when constructing this module's own return value -- never
when reading a record back (see ``authorize_and_get_project_status``'s
own docstring for why the raw, stored record is never translated)."""


@dataclass(frozen=True)
class ProjectStartOutcome:
    """The result of one authorize_and_start_project() call. Unchanged by the fold.

    Attributes:
        decision: The ``planning.run_plan`` outer gate's own real
            ``Decision``. If not granted, nothing else in this outcome
            is meaningful -- the planner never ran at all.
        state: ``"completed"`` or ``"stuck"`` if the outer gate was
            granted and the planner was attempted and returned
            normally; ``None`` if the outer gate was denied. WP-109:
            this is this module's own, unchanged public word for what
            is stored, canonically, as ``"failed"`` -- see module
            docstring.
        reason: The real, human-readable reason the plan is stuck, if
            ``state == "stuck"``; ``None`` otherwise.
        record_identifier: The real task record's own identifier
            (usable with ``jarvis task status`` too, since it shares
            tasks.py's own storage), if a status record was
            successfully written; ``None`` otherwise.
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

    Sequencing is unchanged by the fold, on purpose: ``planning.run_plan``
    is still called first, directly, so this function's own ``decision``
    keeps carrying exactly its own outer-gate classification, never the
    task-record write's. See module docstring for the real, deliberate
    reason this differs from ``tasks.authorize_and_run_task``'s own,
    newer create-then-run sequencing.

    Raises:
        Exception: Any real exception raised either by plan validation
            (``jarvis.application.planning.planner.PlanningError``,
            ``jarvis.application.planning.executor.PlanValidationError``)
            or by a plan step's own wrapped ``authorize_and_*`` call
            during real execution (e.g. ``PathOutsideAllowedScopeError``,
            ``GitCommandFailedError``, ``OSError``, ``sqlite3.Error`` --
            see ``kernel.capability_dispatch.PLAN_STEP_EXECUTORS``). A
            real, canonical ``"failed"`` status record is written first
            in every case (WP-109's own word; this module's own public
            ``"stuck"`` vocabulary is a translation applied only to
            this function's own return value, never to what's stored),
            then the identical, unmodified exception is re-raised. WP-113
            (2026-09-10) widened this from a narrow
            ``(PlanningError, PlanValidationError)`` catch -- unlike
            ``tasks.authorize_and_run_task``, this function writes no
            intermediate "running" record at all, so before this fix a
            step-execution exception left **no status record whatsoever**
            for the goal, not even a "stuck" one -- see
            ``jarvis.kernel.tasks``'s own module docstring for the
            identical finding against its own, differently-shaped gap.
    """
    try:
        decision, result = await authorize_and_run_plan(
            goal,
            provider,
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=chain_path,
        )
    except Exception as exc:
        # WP-113: deliberately broad -- see this function's own Raises
        # docstring for why a narrower catch left a real gap here.
        write_task_record(
            goal,
            "failed",
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

    canonical_status, reason = derive_result_status(result)
    state = _CANONICAL_TO_PROJECT_STATE[canonical_status]
    _write_decision, record_identifier = write_task_record(
        goal,
        canonical_status,
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
    """The result of one authorize_and_get_project_status() call. Unchanged by the fold.

    Attributes:
        decision: The ``Decision`` for the underlying ``memory.retrieve``
            call this reuses -- always granted (``Tier.ALLOW``).
        record: The most recent real task ``MemoryRecord`` whose own
            ``goal`` field exactly matches the queried goal, or
            ``None`` if no such record exists yet.
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

    Filters on ``tasks.TASK_KIND`` now (the fold's one, real, shared
    storage marker), not the old, separate ``"project_goal"`` marker --
    see module docstring for the real, honest broad-recall-then-filter
    approximation this shares with ``job_application.list``/
    ``tasks.authorize_and_list_tasks``, unchanged by the fold.

    **WP-109: the returned record is the real, raw, stored
    ``MemoryRecord``, never translated.** A failed plan's own
    ``record.value.value["status"]`` is the real, canonical
    ``"failed"`` -- not this module's own public ``"stuck"`` word. Only
    the CLI's own printed text (``cli/main.py``) translates it for
    display; this function will not fabricate a record claiming a
    different value was stored than what actually was.
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
        and record.value.value.get("kind") == TASK_KIND
        and record.value.value.get("goal") == goal
    ]
    latest = max(matching, key=lambda record: record.written_at) if matching else None
    return ProjectStatusOutcome(decision=recall_outcome.decision, record=latest)
