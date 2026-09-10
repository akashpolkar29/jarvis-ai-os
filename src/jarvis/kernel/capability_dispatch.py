"""A real, generic capability-dispatch registry for `planning.run_plan` (ADR-0062, M7 design).

**The real gap this module closes**: `AuthorizationOrchestrator.authorize_by_id()`
only ever produces a `Decision` -- it never performs a capability's
real side effect. Every existing capability's real action is hand-
wired into its own dedicated `kernel/*.py` composition function
(`authorize_and_read_file`, `authorize_and_get_git_status`, etc.),
each of which already does its own real "authorize, then, if granted,
act" call internally. A generic planner that only calls
`authorize_by_id()` per step would never actually run anything.

**The real, deliberately small mechanism this module adds**: a
`dict[CapabilityId, PlanStepExecutor]`, `PLAN_STEP_EXECUTORS`, mapping
a capability id to a small adapter function that unpacks a plan
step's own generic `arguments` mapping into that capability's own
real, already-existing `authorize_and_*` composition function --
reusing it completely unmodified, including its own internal
authorization call. Each adapter constructs its own real
registry/storage/chain/orchestrator exactly as its wrapped function
already does (no shared, cross-step orchestrator instance) -- multiple
steps against the same `chain_path` load-append-save the same real
file sequentially, correctly accumulating every step's own decision
into one persisted audit trail, the same way any two independent CLI
invocations against the same `--chain-path` already do.

**Deliberately minimal initial coverage, not exhaustive** (WP-104):
only four real, already-existing, safe (`Tier.ALLOW`) capabilities
were wired at first -- `fs.read_file`, `fs.list_dir`, `git.status`,
`memory.retrieve` -- proving the real mechanism end-to-end without
attempting to wire every one of this codebase's 38+ capabilities in
one pass. Extending coverage to more capabilities is real, incremental
future work, adding one small adapter function per capability,
matching this module's own established shape -- not a structural
change to the mechanism itself.

**WP-114 (2026-09-10) extends `PLAN_STEP_EXECUTORS` itself with three
more real, safe (`Tier.ALLOW`), already-registered, port-free
capabilities** -- `fs.find`, `fs.search_content`, `fs.recent` -- the
exact "one small adapter function per capability" extension this
module's own docstring already anticipated; each already has an
existing, unmodified `authorize_and_*` composition function with a
real, safe default (`allowed_root=Path.home()`), exactly like
`fs.read_file`/`fs.list_dir` above, so no new configuration or port
was needed to wire them here.

**`communications.list_email`/`communications.read_email`/
`communications.list_calendar_events` are deliberately NOT added to
this static dict, and have no sync `PlanStepExecutor` adapter here at
all** -- even though all three are real, registered, `Tier.ALLOW`
capabilities too. Two real, independent reasons, not one: (1) unlike
every entry above, their own `authorize_and_*` functions
(`kernel/communications.py`) require a real `email_port`/
`calendar_port` argument with **no default** (real, per-deployment
IMAP/CalDAV configuration this module cannot supply); (2) those three
functions are `async def`, while `PlanStepExecutor` is a plain, sync
callable -- wrapping an `async` call in `asyncio.run()` here would
raise `RuntimeError` the moment it is invoked from inside
`kernel.router.authorize_and_route`'s own, already-running event loop
(confirmed directly, not assumed, while first writing this). `kernel.router`
therefore dispatches these three directly, with its own real `await`,
only when the matching port was supplied to that specific
`authorize_and_route()` call -- seeing `Email{List,Read}StepResult`/
`CalendarListStepResult` below to keep each response shape
named and typed. `planning.run_plan` (which imports
`PLAN_STEP_EXECUTORS` directly, with no port and no `await` available
to it) never gains these three capabilities -- a deliberate scope
boundary, not an oversight.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from jarvis.application.planning.executor import PlanStepOutcome
from jarvis.kernel.capabilities import (
    FIND_FILES_CAPABILITY_ID,
    GIT_STATUS_CAPABILITY_ID,
    LIST_DIR_CAPABILITY_ID,
    MEMORY_RETRIEVE_CAPABILITY_ID,
    READ_FILE_CAPABILITY_ID,
    RECENT_FILES_CAPABILITY_ID,
    SEARCH_CONTENT_CAPABILITY_ID,
)
from jarvis.kernel.desktop import authorize_and_get_git_status
from jarvis.kernel.files import (
    authorize_and_find_files,
    authorize_and_list_dir,
    authorize_and_list_recent_files,
    authorize_and_read_file,
    authorize_and_search_content,
)
from jarvis.kernel.memory import authorize_and_recall

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from jarvis.domain.calendar import CalendarEvent
    from jarvis.domain.capability import CapabilityId
    from jarvis.domain.email import EmailMessage, EmailSummary
    from jarvis.domain.policy import Decision
    from jarvis.domain.provenance import Tainted

    PlanStepExecutor = Callable[[Mapping[str, object], bool, bool, Path], PlanStepOutcome]

DEFAULT_EMAIL_FOLDER = "INBOX"
"""Mirrors `jarvis email list --folder`'s own real CLI default exactly (cli/main.py)."""

DEFAULT_EMAIL_LIST_LIMIT = 10
"""Mirrors `jarvis email list --limit`'s own real CLI default exactly (cli/main.py)."""


def _execute_read_file(
    arguments: Mapping[str, object],
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
) -> PlanStepOutcome:
    outcome = authorize_and_read_file(
        Path(str(arguments["path"])),
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
    )
    return PlanStepOutcome(decision=outcome.decision, result=outcome)


def _execute_list_dir(
    arguments: Mapping[str, object],
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
) -> PlanStepOutcome:
    outcome = authorize_and_list_dir(
        Path(str(arguments["path"])),
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
    )
    return PlanStepOutcome(decision=outcome.decision, result=outcome)


def _execute_git_status(
    arguments: Mapping[str, object],
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
) -> PlanStepOutcome:
    outcome = authorize_and_get_git_status(
        Path(str(arguments["repo_dir"])),
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
    )
    return PlanStepOutcome(decision=outcome.decision, result=outcome)


def _execute_memory_recall(
    arguments: Mapping[str, object],
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
) -> PlanStepOutcome:
    raw_limit = arguments.get("limit", 5)
    limit = raw_limit if isinstance(raw_limit, int) else int(str(raw_limit))
    outcome = authorize_and_recall(
        str(arguments["query"]),
        limit=limit,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
    )
    return PlanStepOutcome(decision=outcome.decision, result=outcome)


def _execute_find_files(
    arguments: Mapping[str, object],
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
) -> PlanStepOutcome:
    outcome = authorize_and_find_files(
        str(arguments["pattern"]),
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
    )
    return PlanStepOutcome(decision=outcome.decision, result=outcome)


def _execute_search_content(
    arguments: Mapping[str, object],
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
) -> PlanStepOutcome:
    outcome = authorize_and_search_content(
        str(arguments["query"]),
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
    )
    return PlanStepOutcome(decision=outcome.decision, result=outcome)


_DEFAULT_RECENT_FILES_LIMIT = 20
"""Mirrors `jarvis fs recent --limit`'s own real CLI default exactly (cli/main.py)."""


def _execute_recent_files(
    arguments: Mapping[str, object],
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
) -> PlanStepOutcome:
    raw_limit = arguments.get("limit", _DEFAULT_RECENT_FILES_LIMIT)
    limit = raw_limit if isinstance(raw_limit, int) else int(str(raw_limit))
    outcome = authorize_and_list_recent_files(
        limit=limit,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
    )
    return PlanStepOutcome(decision=outcome.decision, result=outcome)


PLAN_STEP_EXECUTORS: dict[CapabilityId, PlanStepExecutor] = {
    READ_FILE_CAPABILITY_ID: _execute_read_file,
    LIST_DIR_CAPABILITY_ID: _execute_list_dir,
    GIT_STATUS_CAPABILITY_ID: _execute_git_status,
    MEMORY_RETRIEVE_CAPABILITY_ID: _execute_memory_recall,
    FIND_FILES_CAPABILITY_ID: _execute_find_files,
    SEARCH_CONTENT_CAPABILITY_ID: _execute_search_content,
    RECENT_FILES_CAPABILITY_ID: _execute_recent_files,
}


@dataclass(frozen=True)
class EmailListStepResult:
    """A `communications.list_email` plan step's own real result.

    `authorize_and_list_email` returns a bare `(Decision, summaries)`
    tuple, not a named `*Outcome` dataclass the way every other
    wrapped function above already does -- this module builds this
    small, local wrapper rather than changing that already-shipped,
    already-tested kernel function's own public return shape (which
    would also mean updating its existing CLI call site,
    `cli/main.py::_run_email_subcommand`, real, avoidable ripple this
    module's own "reuse completely unmodified" precedent exists to
    avoid).
    """

    decision: Decision
    summaries: tuple[Tainted[EmailSummary], ...] | None


@dataclass(frozen=True)
class EmailReadStepResult:
    """A `communications.read_email` plan step's own real result. See `EmailListStepResult`."""

    decision: Decision
    message: Tainted[EmailMessage] | None


@dataclass(frozen=True)
class CalendarListStepResult:
    """A `communications.list_calendar_events` plan step's own real result.

    See `EmailListStepResult`'s own docstring for why this small
    wrapper exists rather than changing `authorize_and_list_calendar_events`'s
    own already-shipped return shape.
    """

    decision: Decision
    events: tuple[Tainted[CalendarEvent], ...] | None
