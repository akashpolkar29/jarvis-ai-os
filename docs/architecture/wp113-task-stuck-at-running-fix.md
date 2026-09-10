# WP-113: fixing "task stuck at running" on an uncaught plan-step exception (2026-09-10)

## Status

Real, implemented. No new `CapabilityId`/`Effect`/`Tier`, no ADR --
this is a pure error-handling correctness fix to two already-classified
code paths (`tasks.authorize_and_run_task`'s `memory.update`-based
status transitions, `project.authorize_and_start_project`'s identical
reuse), not a new authorization decision.

Roadmap numbering checked directly before starting: the highest real
`WP-\d+` reference was 112 (WP-112, task-execution trigger). The one
`WP-124` mention in `CLAUDE.md` is a proposed implementation-order
range from a read-only UI-architecture design artifact, never built --
confirmed by reading its own surrounding sentence before treating it
as a real collision. WP-113 was genuinely free.

Self-scoped: the user's own instruction was "continue work" following
a prior `AskUserQuestion` selection of "Task-execution trigger from UI"
(WP-112); WP-112's own final report named this exact limitation and
recommended it as the next work package, which this one is.

## The real gap this closes

WP-112's own design doc found, live-verified, and deliberately left
open a real limitation: `kernel.tasks.authorize_and_run_task`'s
exception handling caught only `(PlanningError, PlanValidationError)`
-- the two exceptions `application/planning/planner.py`'s
`generate_plan` and `executor.py`'s `_validate_plan` can raise during
*pre-flight* plan validation, before any step runs. It did not catch
any exception raised *during* real step execution -- `execute_plan`'s
own per-step loop calls into a plan-step executor
(`kernel.capability_dispatch.PLAN_STEP_EXECUTORS`), which wraps a
real, already-existing `authorize_and_*` composition function
completely unmodified. That function's own real exceptions (the ones
it already documents in its own docstring for its direct CLI callers)
propagated straight up through `execute_plan` -> `authorize_and_run_plan`
-> `authorize_and_run_task`, uncaught anywhere in that chain.

**The real consequence, live-verified in WP-112**: a task whose plan
named a step that raised, e.g., `PathOutsideAllowedScopeError`, was
left with its stored status at `"running"` permanently -- every
subsequent `jarvis task status`/`GET /api/tasks/<id>` call would keep
reporting `"running"` forever, even though the task had, in fact,
failed and stopped executing.

## Investigating before fixing: a second, real, related gap

Before writing any code, `kernel.project.py` (the other real caller of
`authorize_and_run_plan`, `authorize_and_start_project`) was checked
directly, since it shares the identical call chain. It has the
*identical* narrow `except (PlanningError, PlanValidationError)`
clause -- but `project.py` writes no intermediate `"running"` record
at all (unlike `tasks.py`'s own deliberate create-then-run split, WP-107).
So a step-execution exception there did not leave a task "stuck" at a
visible status -- it left **no status record whatsoever** for the
goal. `jarvis project status "<goal>"` would report nothing had ever
been attempted, silently, for a goal that genuinely had been. This is
the same root cause manifesting as a different, arguably worse symptom
(total silence, not a misleading-but-visible status) -- fixed here
too, for the same reason and by the same mechanism.

## The fix: widen to `except Exception`, deliberately, not a curated list

Both functions' own `except (PlanningError, PlanValidationError)`
clauses became `except Exception as exc:`, with the identical,
unmodified exception still re-raised afterward -- the caller (`jarvis
task run`, `jarvis project start`, `POST /api/tasks/<id>/run`) sees
exactly the same real exception it always did; only the underlying
task/project record's own stored status changed, from "never
updated"/"stuck forever" to `"failed"`, with `f"{type(exc).__name__}: {exc}"`
as the reason, matching the existing `PlanningError`/`PlanValidationError`
reason format exactly.

**Why not a curated exception tuple naming today's real, wired
exception types instead**: the four capabilities currently wired into
`PLAN_STEP_EXECUTORS` (`fs.read_file`, `fs.list_dir`, `git.status`,
`memory.retrieve`) were investigated directly, not guessed, to
understand the real scope of this bug --

- `fs.read_file`/`fs.list_dir`: `PathOutsideAllowedScopeError`
  (`kernel/files.py`, a bare `Exception` subclass), plus real
  underlying `OSError` (missing/unreadable file) and `UnicodeDecodeError`
  (non-UTF-8 content) from `LocalFileSystemAdapter.read_text`'s real
  `path.read_text(encoding="utf-8")` call.
- `git.status`: `GitCommandFailedError` (`ports/git.py`, also a bare
  `Exception` subclass, raised by `adapters/git.py` on a non-zero exit
  code).
- `memory.retrieve`: `sqlite3.Error`/`sqlite3.DatabaseError` (a
  corrupted database file -- the identical class of gap
  `CLAUDE.md`'s own "Phase 2, resilience against corrupted persistent
  state" pass already found and fixed for the CLI/voice-loop entry
  points).

A tuple naming exactly these would have "fixed" today's real bug --
but it would silently reintroduce the identical bug the moment
`PLAN_STEP_EXECUTORS` gains a fifth capability whose own
`authorize_and_*` function raises something not already in that list
(a real, likely event -- `capability_dispatch.py`'s own module
docstring already states "extending coverage to more capabilities is
real, incremental future work"). `except Exception` is the deliberate,
structural choice instead: it closes this bug for every capability
`PLAN_STEP_EXECUTORS` could ever hold, present or future, with no
ongoing maintenance coupling between this except clause and that
registry's own contents.

**Scope, stated precisely**: `except Exception`, never `except
BaseException` -- `KeyboardInterrupt`/`SystemExit`/`GeneratorExit`
still propagate immediately, exactly as before this change; this
widening only affects exceptions that were already, structurally,
"a real failure this codebase's own CLI already documents and handles
cleanly for its own direct callers," never process-control signals.

This is a considered, documented exception to this project's own
general preference for precise, curated exception lists over blanket
catches (see, e.g., `_HANDLED_TASK_RUN_ERRORS` in `cli/ui_server.py`,
or the CLI's own explicit, enumerated `except (...)` tuple in
`cli/main.py::main()`) -- named as such directly in both functions'
own docstrings and inline comments, not silently substituted for the
established convention.

## Testing

Two new real regression tests, one per fixed function
(`tests/unit/test_tasks_kernel.py::test_run_on_a_step_execution_exception_marks_the_task_failed_not_stuck_at_running`,
`tests/unit/test_project_kernel.py::test_a_step_execution_exception_still_records_a_failed_status`):
each drives a real, structurally-valid single-step plan naming the
real, already-wired `fs.read_file` capability with a path outside its
`allowed_root` (`Path.home()` monkeypatched to a real `tmp_path`
subdirectory, then a plan step targeting `/etc/passwd`, mirroring
`test_planning_kernel.py`'s own established `Path.home()`-monkeypatch
pattern) -- proving both that the real `PathOutsideAllowedScopeError`
still propagates to the caller unmodified, and that the stored record
now correctly shows `"failed"` with that exception named in its own
`reason` field, rather than staying at `"running"` (`tasks.py`) or not
existing at all (`project.py`).

## Security / authorization -- unchanged

No new `CapabilityId`/`Effect`/`Tier`. `application/planning/executor.py`
(ADR-0062's own per-step authorization, no batch pre-approval) and the
authorization kernel itself were not touched -- this fix operates
entirely in the two composition-root functions that already wrap
`authorize_and_run_plan`, changing only which exceptions cause a
status-record write before re-raising. `execute_plan`'s own real
per-step authorization behavior (each step individually authorized,
exactly when it runs) is identical before and after this change.
