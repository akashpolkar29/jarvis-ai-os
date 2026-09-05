# Release-readiness / versioning consistency check (5 mixed real tasks, Task 5)

## Status

Real, evidence-based audit. Date: 2026-09-05.

## Real, confirmed baseline

`git status` was clean before this task started; no stray or
accidentally-tracked build artifacts exist in the repository (checked
directly, not assumed). `src/jarvis/py.typed` already exists (PEP
561), correctly signaling that `jarvis.plugin_api` -- meant to be
imported by real plugin authors -- ships inline type information.
Real git tag messages (checked directly, e.g. `v0.6.0`'s own full
message) are detailed and accurate, not placeholder text.

## Real gap found and fixed: `pyproject.toml`'s own version had never been bumped

`version = "0.1.0.dev0"` -- confirmed, by reading `pyproject.toml`
directly, to be the *exact, original* string this field has held since
this project's very first commit, despite 7 real git tags since (`v0.1.0`
through `v0.6.0`) and six code-complete milestones. This is a real,
concrete versioning inconsistency: the one place Python's own packaging
tooling (`pip show jarvis`, `importlib.metadata.version("jarvis")`, a
future PyPI publish) would report this project's version has never
once matched reality.

**Fixed**: bumped to `"0.6.0"`, matching the most recent real git tag
exactly. A deliberately conservative, mechanical correction -- it
does not attempt to guess or assert a version ahead of the last real
tag (e.g. a `.dev0`-suffixed "next version in progress" string), since
picking that number is a real decision this task has no grounds to
make unilaterally. Whether to adopt an ongoing per-tag bump convention,
or a dynamic-versioning tool (e.g. `hatch-vcs`, deriving the version
from git tags automatically so this field can never drift again), is
left for the user's own decision -- named here as a real, concrete
option, not silently adopted.

## Real gap found and fixed: no `--version` flag existed

`jarvis --version` previously failed with `error: the following
arguments are required: command` -- confirmed directly, not assumed.
There was no way to check which version of `jarvis` was installed via
the CLI itself, a standard convention essentially every real CLI tool
provides. **Fixed**: a real `--version` flag added to the top-level
parser, reading `importlib.metadata.version("jarvis")` -- the actual,
installed package's own real version, which will automatically track
whatever `pyproject.toml` says at build time, rather than a second,
independently-drifting hardcoded string. A new, real, unmocked test
confirms it prints the real, installed version and exits `0`.

## Real, honest finding: no `CHANGELOG.md` exists

Confirmed directly -- no changelog file exists anywhere in this
repository. This project's own real history is extensively recorded
elsewhere (`CLAUDE.md`'s own running "Current Status" log, real,
detailed git tag messages, `docs/threat-model/v0.md`'s own dated
findings log), but none of these are a `CHANGELOG.md` a real user
reading a release would expect to find. **Not built here**: authoring
a genuine, accurate changelog covering six real, code-complete
milestones' worth of work packages would be a substantial undertaking
in its own right, and a rushed, incomplete one authored under this
task's own time budget risks being less trustworthy than no changelog
at all, given this project's own stated "state findings honestly,
don't round up" discipline. Flagged here as a real, concrete gap for
the user's own future decision, not silently built partial or skipped
without mention.

## Real, already-known, not re-litigated: M3's own deliberate non-tag

`CLAUDE.md`'s own opening line already states M3 (desktop control) is
code-complete but deliberately untagged, "a deliberately separate,
later action neither pass touched." Re-confirmed here as still true
and still intentional, not a new finding, and not treated as a gap
this task should close (tagging is an action with its own real
consequences the user should take deliberately, not a byproduct of a
versioning-consistency audit).

## Conclusion

Two real, concrete versioning gaps found and fixed (a version string
that had never once matched any real tag; a missing, standard
`--version` flag). One real, honest gap named and deliberately not
acted on (no `CHANGELOG.md`) rather than built hastily. Everything
else checked (working-tree cleanliness, `py.typed`, tag message
quality, M3's own tagging status) confirmed already in good order, not
re-derived from scratch.
