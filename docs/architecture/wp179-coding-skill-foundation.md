# Coding/development skill foundation (WP-179)

## Status

Real, implemented (one new `SkillDescriptor`, purely declarative). No
ADR -- no new `CapabilityId`/`Effect`/`Tier`, no new execution
mechanism, no `terminal.run` change, no second shell mechanism of any
kind.

## What was built

A new skill, `coding` (`kernel/skills.py::CODING_SKILL_ID`), grouping
five already-registered capabilities directly matching this work
package's own five named areas:

| Named area | Capability |
|---|---|
| repository inspection | `git.status` |
| file reading | `fs.read_file` |
| code search | `fs.find`, `fs.search_content` |
| tests, development workflows | `coding.run_task` |

`coding.run_task` (WP-71's already-built coding-loop wrapper) is the
real "development workflow" capability -- it already writes code and
runs real tests internally, through its own real escalation ladder, in
a disposable, sandboxed workspace per climb (ADR-0055/ADR-0056), with
every real write separately gated by `Effect.CODE_WRITE`/
`Effect.PROTECTED_PATH_WRITE`. This skill does not add a "run tests"
capability of its own -- none is statically registered as a standalone
capability, and `coding.run_task`'s own internal test execution
already covers the real need without a new one.

## A real, deliberate scope decision: no git write capabilities

`git.create_branch`/`git.commit`/`git.push`/`git.force_push` are real,
already-registered, already-stable capabilities -- but none of this
work package's own five named areas ("repository inspection, file
reading, code search, tests, development workflows") describes
committing or pushing, and each of those four is already its own,
separately-discoverable capability in the real registry (already
visible via `jarvis skills show` once a "Desktop"/"Git" skill exists,
a real, out-of-scope future addition, mirroring how WP-173 itself
deferred desktop control entirely). Including them here would be the
same kind of unjustified scope creep the Research skill's design note
(WP-178) already reasoned against for `job_search.*` -- padding a
skill's `capability_ids` to look more complete rather than to
accurately describe what was actually asked for.

## How the hard rules were honored

- **No automatic execution of destructive shell commands**: this
  skill is pure discovery metadata -- it cannot execute anything by
  construction (`SkillDescriptor` carries no `Effect`/`Tier`, no
  callable). `coding.run_task` itself never runs an arbitrary shell
  command either; its real test execution goes through
  `ValidationPort`'s own already-existing, already-scrutinized
  mechanism, unmodified by this work package.
- **`terminal.run`/`SyntheticInputPort` untouched**: neither is
  referenced by this skill's `capability_ids`, and neither file was
  opened or modified.
- **No second shell execution mechanism**: nothing here constructs a
  subprocess, a shell, or any execution path outside the exact,
  pre-existing `coding.run_task` capability and its own, unmodified
  internals (`Dispatcher`/`EscalationLadder` -- both explicitly
  off-limits per this queue's hard rules, and neither was touched).

## Testing

`tests/unit/test_skills.py`: the skill registry now registers exactly
8 skills (up from 7); a dedicated test confirms the Coding skill's
`capability_ids` is exactly the five capabilities named above --
explicitly asserting the set, which would fail if a git write
capability were ever added by mistake -- and that it carries real
`instructions`. `build_default_skill_registry()` continuing to
validate cleanly is itself proof this skill names nothing invented.
