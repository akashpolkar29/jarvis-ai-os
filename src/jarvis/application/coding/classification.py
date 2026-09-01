"""Classification -> Effect mapping for M5's coding-agent file-write capability (ADR-0056).

Kept separate from ``writer.py`` deliberately, mirroring
``jarvis.application.memory.classification``'s own split exactly: this
is the one pure decision ("given this real target path, which
``Effect`` must a coding-agent write declare") a real authorizer
orchestrates around.

**A real technical correction ADR-0056 itself already records, not
repeated here**: a single ``Effect`` cannot float at two different
tiers depending on which path an invocation carries
(``domain/capability.py``'s ``_EFFECT_TIER_FLOOR`` is one fixed floor
per member). This module's own :func:`code_write_effect_for` resolves
that the same way ``memory_effect_for`` resolves the analogous
``Classification.SECRET`` gap: a second, distinct effect
(``Effect.PROTECTED_PATH_WRITE``), chosen per invocation.

**A second, real gap ADR-0056's own amendment closes, built for real
here**: the working assumption's default ``protected_patterns``
(``test_*.py``, ``*_test.py``, ``tests/*``) are Python/pytest-specific,
but a real coding-agent invocation targets an arbitrary repository,
most of which will not be Python/pytest projects at all. A default
drawn only from this project's own convention would silently fail to
protect a Go, JavaScript, or Ruby repository's own real test files --
the DENY floor would simply never fire, with no one aware it hadn't.
:func:`detect_protected_patterns` and :func:`resolve_protected_patterns`
are the real, fail-closed fix: detect a real, checkable signal of the
target repository's own test convention, or refuse to authorize any
write at all rather than silently defaulting to patterns that do not
apply.
"""

from __future__ import annotations

import configparser
import json
import tomllib
from fnmatch import fnmatch
from typing import TYPE_CHECKING

from jarvis.domain.capability import Effect

if TYPE_CHECKING:
    from pathlib import Path

_PYTEST_DEFAULT_PATTERNS: tuple[str, ...] = ("test_*.py", "*_test.py")
"""pytest's own real, built-in default `python_files` discovery pattern,
unmodified -- see ADR-0056's own Context section for why this project's
own narrower, real convention (test_*.py only) is not used as the
default here: a target repository is not necessarily this one."""

_GO_DEFAULT_PATTERNS: tuple[str, ...] = ("*_test.go",)
"""Go's own real tooling convention: `go build`/`go test` themselves
(not just community style) treat any `_test.go`-suffixed file
specially -- confirmed live via web search against Go's own
documentation before writing this, not assumed from general knowledge
alone (see this work package's own commit message for the real
sources)."""

_RSPEC_DEFAULT_PATTERNS: tuple[str, ...] = ("*_spec.rb", "spec/*")
"""RSpec's own real, documented convention: a bare `rspec` invocation
only runs `*_spec.rb` files inside a `spec/` directory -- confirmed
live via web search against RSpec's own documentation."""

_JEST_LIKE_DEFAULT_PATTERNS: tuple[str, ...] = (
    "*.test.js",
    "*.test.jsx",
    "*.test.ts",
    "*.test.tsx",
    "*.spec.js",
    "*.spec.jsx",
    "*.spec.ts",
    "*.spec.tsx",
    "__tests__/*",
)
"""A real, fnmatch-compatible approximation of Jest's own documented
default testMatch (`**/__tests__/**/*.[jt]s?(x)`,
`**/?(*.)+(spec|test).[jt]s?(x)`) -- confirmed live via web search
against Jest's own documentation. Not a literal translation:
`fnmatch` supports `*`/`?`/`[seq]` only, not glob's `**`/brace-group
syntax, so this is a real, honest simplification, not an exact
reproduction -- stated plainly rather than implied to be identical.
Reused for Vitest, whose own real default closely mirrors Jest's."""

_MOCHA_DEFAULT_PATTERNS: tuple[str, ...] = ("test/*",)
"""Mocha's own real, weaker default: a bare `mocha` invocation looks
under `./test` with no further built-in file-naming convention beyond
that directory -- a real, broader, less precise default than
Jest/Vitest's, stated as such, not overstated."""

_JS_TEST_FRAMEWORK_PATTERNS: dict[str, tuple[str, ...]] = {
    "jest": _JEST_LIKE_DEFAULT_PATTERNS,
    "vitest": _JEST_LIKE_DEFAULT_PATTERNS,
    "mocha": _MOCHA_DEFAULT_PATTERNS,
}
"""Checked in this fixed order against package.json's own real
dependencies -- a real, stated limitation, not hidden: a repository
declaring more than one of these picks whichever is checked first
(jest, then vitest, then mocha), not a real attempt to reconcile
multiple real frameworks in one repository."""


class UnrecognizedTestConventionError(Exception):
    """Raised when a target repository's own real test convention could not be detected.

    The real, deliberate fail-closed outcome ADR-0056's own amendment
    requires: rather than silently falling back to Python/pytest
    patterns that may not apply to this repository at all,
    :func:`resolve_protected_patterns` raises this and refuses to
    authorize any coding-agent write until the caller supplies real,
    explicit ``protected_patterns`` itself.
    """


def code_write_effect_for(path: Path, protected_patterns: tuple[str, ...]) -> Effect:
    """Return the Effect a coding-agent file-write CapabilityInvocation must declare for `path`.

    ``path`` must be relative to the target repository's own root --
    ``protected_patterns`` like ``tests/*`` are matched against
    ``str(path)`` via `fnmatch`, which has no notion of a repository
    root of its own; an absolute path would silently never match a
    directory-prefix pattern like ``tests/*`` at all. Callers are
    responsible for this real precondition; this function does not
    (and, given a bare ``Path``, structurally cannot) verify it.

    Effect.PROTECTED_PATH_WRITE (floors Tier.DENY) if `path` matches any
    of `protected_patterns` (fnmatch-style glob, matching this
    project's own already-established `git`/patch-adjacent tooling
    conventions rather than inventing a new pattern language) --
    unconditional, no confirmation overrides it, matching
    ADR-0038/ADR-0049's own precedent for "this class of write is
    never allowed, full stop." Effect.CODE_WRITE (floors Tier.CONFIRM)
    for every other path -- ordinary coding-agent writes, gated the
    same way any other local write already is, not specially
    restricted beyond that by this ADR.
    """
    if any(fnmatch(str(path), pattern) for pattern in protected_patterns):
        return Effect.PROTECTED_PATH_WRITE
    return Effect.CODE_WRITE


def _pyproject_has_pytest_section(pyproject_path: Path) -> bool:
    try:
        with pyproject_path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return False
    tool = data.get("tool")
    return isinstance(tool, dict) and "pytest" in tool


def _ini_file_has_section(path: Path, section: str) -> bool:
    parser = configparser.ConfigParser()
    try:
        read_files = parser.read(path, encoding="utf-8")
    except configparser.Error:
        return False
    return bool(read_files) and parser.has_section(section)


def _gemfile_mentions_rspec(gemfile_path: Path) -> bool:
    try:
        text = gemfile_path.read_text(encoding="utf-8")
    except OSError:
        return False
    return "rspec" in text


def _detect_js_test_patterns(package_json_path: Path) -> tuple[str, ...] | None:
    try:
        data = json.loads(package_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    dependencies = data.get("dependencies")
    dev_dependencies = data.get("devDependencies")
    known_dependencies: set[str] = set()
    if isinstance(dependencies, dict):
        known_dependencies.update(dependencies)
    if isinstance(dev_dependencies, dict):
        known_dependencies.update(dev_dependencies)
    for framework, patterns in _JS_TEST_FRAMEWORK_PATTERNS.items():
        if framework in known_dependencies:
            return patterns
    return None


def detect_protected_patterns(repo_root: Path) -> tuple[str, ...] | None:
    """Detect a real, checkable test-file convention at `repo_root`, or return None.

    Real, bounded detection, not an exhaustive survey of every
    possible ecosystem -- checked, in order, against real, documented
    signals for the languages/frameworks with the clearest real
    convention to detect (see each pattern constant's own docstring
    for the real source):

    1. Python/pytest -- `pytest.ini`, `pyproject.toml`'s
       `[tool.pytest.ini_options]` (checked via real TOML parsing, not
       a substring scan), `setup.cfg`'s `[tool:pytest]`, or `tox.ini`'s
       `[pytest]` (checked via real INI parsing).
    2. Go -- a real `go.mod` file (marks a real Go module).
    3. Ruby/RSpec -- a real `.rspec` config file, or a `Gemfile`
       mentioning `rspec`.
    4. JavaScript/TypeScript -- a real `package.json` whose own real
       dependencies name a known test framework (jest, vitest, mocha).

    Returns:
        A real, non-empty tuple of `protected_patterns`, or ``None`` if
        no recognized real convention was found -- a genuine, expected
        outcome for many real repositories (plain Python `unittest`
        with no pytest config, Rust -- whose own real test convention
        is largely *inline* `#[cfg(test)]` code a filename pattern
        cannot protect at all, not just a detection gap -- Java/Maven/
        Gradle, and any repository this function's own bounded real
        research did not cover), never guessed at.
    """
    signals: tuple[tuple[bool, tuple[str, ...]], ...] = (
        ((repo_root / "pytest.ini").is_file(), _PYTEST_DEFAULT_PATTERNS),
        (_pyproject_has_pytest_section(repo_root / "pyproject.toml"), _PYTEST_DEFAULT_PATTERNS),
        (_ini_file_has_section(repo_root / "setup.cfg", "tool:pytest"), _PYTEST_DEFAULT_PATTERNS),
        (_ini_file_has_section(repo_root / "tox.ini", "pytest"), _PYTEST_DEFAULT_PATTERNS),
        ((repo_root / "go.mod").is_file(), _GO_DEFAULT_PATTERNS),
        ((repo_root / ".rspec").is_file(), _RSPEC_DEFAULT_PATTERNS),
        (_gemfile_mentions_rspec(repo_root / "Gemfile"), _RSPEC_DEFAULT_PATTERNS),
    )
    for detected, patterns in signals:
        if detected:
            return patterns

    package_json = repo_root / "package.json"
    if package_json.is_file():
        js_patterns = _detect_js_test_patterns(package_json)
        if js_patterns is not None:
            return js_patterns

    return None


def resolve_protected_patterns(
    repo_root: Path, explicit_patterns: tuple[str, ...] | None = None
) -> tuple[str, ...]:
    """Return the real `protected_patterns` to use for `repo_root` -- fail-closed, never guessed.

    Args:
        repo_root: The target repository's own real root directory.
        explicit_patterns: A real, caller-supplied override -- if
            given, always wins, matching ADR-0056's own "configurable,
            not hardcoded" requirement. ``None`` means "detect it."

    Returns:
        `explicit_patterns` if given; otherwise whatever
        :func:`detect_protected_patterns` finds.

    Raises:
        UnrecognizedTestConventionError: If `explicit_patterns` is
            ``None`` and no real convention could be detected --
            ADR-0056's own real, required fail-closed behavior: no
            target repository is ever silently treated as "protected"
            by patterns that were never actually confirmed to match
            its own real convention.
    """
    if explicit_patterns is not None:
        return explicit_patterns
    detected = detect_protected_patterns(repo_root)
    if detected is None:
        msg = (
            f"Could not detect a real, recognized test-file convention for {repo_root}. "
            "Refusing to authorize any coding-agent write without explicit "
            "protected_patterns -- see ADR-0056's own amendment for why."
        )
        raise UnrecognizedTestConventionError(msg)
    return detected
