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

**Deliberately minimal initial coverage, not exhaustive**: only four
real, already-existing, safe (`Tier.ALLOW`) capabilities are wired
here -- `fs.read_file`, `fs.list_dir`, `git.status`, `memory.retrieve`
-- proving the real mechanism end-to-end without attempting to wire
every one of this codebase's 38+ capabilities in one pass. Extending
coverage to more capabilities is real, incremental future work, adding
one small adapter function per capability, matching this module's own
established shape -- not a structural change to the mechanism itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from jarvis.application.planning.executor import PlanStepOutcome
from jarvis.kernel.capabilities import (
    GIT_STATUS_CAPABILITY_ID,
    LIST_DIR_CAPABILITY_ID,
    MEMORY_RETRIEVE_CAPABILITY_ID,
    READ_FILE_CAPABILITY_ID,
)
from jarvis.kernel.desktop import authorize_and_get_git_status
from jarvis.kernel.files import authorize_and_list_dir, authorize_and_read_file
from jarvis.kernel.memory import authorize_and_recall

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from jarvis.domain.capability import CapabilityId

    PlanStepExecutor = Callable[[Mapping[str, object], bool, bool, Path], PlanStepOutcome]


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


PLAN_STEP_EXECUTORS: dict[CapabilityId, PlanStepExecutor] = {
    READ_FILE_CAPABILITY_ID: _execute_read_file,
    LIST_DIR_CAPABILITY_ID: _execute_list_dir,
    GIT_STATUS_CAPABILITY_ID: _execute_git_status,
    MEMORY_RETRIEVE_CAPABILITY_ID: _execute_memory_recall,
}
