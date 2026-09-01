"""Mechanical enforcement of ADR-0056's own required "single write path" guarantee.

ADR-0056 grants `Effect.PROTECTED_PATH_WRITE` an unconditional
`Tier.DENY` floor for a coding-agent write matching a protected test
path -- but that guarantee only holds if a real caller genuinely
classifies *every* real write (via
`jarvis.application.coding.classification.code_write_effect_for`/
`jarvis.application.coding.writer.CodeWriteAuthorizer`) before it ever
reaches `WorkspacePort.apply_patch`. The required fix, named explicitly
in that ADR's own Consequences section, mirrors
`tests/meta/test_memory_adapter_isolation.py`'s own technique exactly
(itself ADR-0049's own precedent): AST-scan every module under
`src/jarvis` *except* a real, explicit allowlist, asserting
`apply_patch` is never referenced there.

**A real, checked-directly finding this allowlist is built on, not
assumed**: `WorkspacePort.apply_patch` (`ports/workspace.py`) and
`LocalWorkspaceAdapter.apply_patch` (`adapters/workspace.py`) are
*method definitions* -- `ast.FunctionDef.name` is a plain string
attribute, never visited as an `ast.Name`/`ast.Attribute` node by
`referenced_code_identifiers`'s own real AST walk (confirmed directly
against both real files before writing this allowlist, not assumed).
Neither module needs its own exemption; only real *callers* of
`apply_patch` do.

**One real, already-existing, legitimate caller, confirmed by a real,
repo-wide grep before writing this test**:
`adapters/validation/_command.py`'s own `apply_candidate_or_report_unverifiable`
(M2, ADR-0043) calls `workspace.apply_patch(candidate.content)` to
materialize a Candidate for validation -- real, already-Accepted
infrastructure entirely unrelated to this ADR's own coding-agent
concern, predating it, not a violation. Named here explicitly as a
real, deliberate allowlist entry, not silently ignored.

**Real, explicit sequencing note, resolved -- not a silent gap**: this
test module was built in WP-70, before WP-71 (the coding-loop wrapper
itself). At the time, it named a real, deeper open question: would
WP-71 call `apply_patch` directly, or by constructing a wrapping
`WorkspacePort` that intercepts the call M2's own
`Dispatcher`→`ValidationPort` chain makes internally? Resolved by
WP-71/ADR-0055's own "Amendment 2026-09-01" (see
`docs/adr/0055-...md`): no interception is possible or needed --
`Dispatcher.run()`'s own internal `apply_patch` calls only ever touch a
disposable, `SandboxPort`-backed workspace copy (WP-73), never the real
target repository. `application/coding/loop.py`'s own
`run_coding_task` calls `WorkspacePort.apply_patch` directly, itself,
exactly once, against a *second*, distinct `WorkspacePort` pointed at
the real repository -- only after the winning candidate's own touched
paths are individually authorized (`CodeWriteAuthorizer`, WP-70) and
every single one is granted. Added to this allowlist below, the same
"small, tracked, mechanical addition"
`test_memory_adapter_isolation.py`'s own sequencing note predicted.
"""

from __future__ import annotations

from pathlib import Path

from tests.meta.helpers import iter_py_files, referenced_code_identifiers

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"

_BANNED_IDENTIFIER = "apply_patch"


def _references_identifier_outside_allowed_modules(
    src_root: Path, banned_identifier: str, allowed_modules: frozenset[Path]
) -> list[Path]:
    """Return files under ``src_root``, outside ``allowed_modules``, referencing the identifier."""
    return [
        py_file
        for py_file in iter_py_files(src_root)
        if py_file not in allowed_modules
        and banned_identifier in referenced_code_identifiers(py_file.read_text(encoding="utf-8"))
    ]


def test_the_scan_predicate_actually_detects_a_violation() -> None:
    """The predicate genuinely fires on a real violation, not just passes on a clean tree."""
    violating_snippet = (
        "def bypass(workspace, candidate):\n    workspace.apply_patch(candidate.content)\n"
    )

    identifiers = referenced_code_identifiers(violating_snippet)

    assert _BANNED_IDENTIFIER in identifiers


def test_the_scan_predicate_ignores_docstrings_that_merely_discuss_the_guarantee() -> None:
    """Prose explaining this restriction (naming apply_patch) must not itself be a violation.

    This is the exact false-positive case a naive substring scan would
    hit -- and does hit, on this very module's own docstring, which
    correctly names "apply_patch" in prose to document the rule.
    """
    documentation_only_snippet = (
        '"""This module must classify every write before calling apply_patch.\n'
        "\n"
        "See ADR-0056.\n"
        '"""\n'
        "\n"
        "SOME_CONSTANT = 1\n"
    )

    identifiers = referenced_code_identifiers(documentation_only_snippet)

    assert _BANNED_IDENTIFIER not in identifiers


def test_the_scan_predicate_does_not_flag_a_bare_method_definition() -> None:
    """A real, checked-directly finding: defining apply_patch is not the same as calling it.

    ``ast.FunctionDef.name`` is never visited as an ``ast.Name``/
    ``ast.Attribute`` node -- confirmed here as a real, proven property
    of the shared scan predicate, not just asserted in this module's
    own docstring.
    """
    definition_only_snippet = "def apply_patch(self, patch: str) -> None:\n    ...\n"

    identifiers = referenced_code_identifiers(definition_only_snippet)

    assert _BANNED_IDENTIFIER not in identifiers


def test_no_module_under_src_references_apply_patch_outside_the_real_allowlist() -> None:
    """The real ADR-0056 guarantee: apply_patch is referenced only where it legitimately must be.

    Two real, deliberate entries, both named in this module's own
    docstring: ``adapters/validation/_command.py`` (the pre-existing
    M2/ADR-0043 caller, applying a candidate to a disposable workspace
    for validation) and ``application/coding/loop.py`` (WP-71's own
    coding-loop wrapper, the one real place a *classified, authorized*
    write against the actual target repository happens, exactly once,
    only after every touched path is granted).
    """
    validation_command = SRC_ROOT / "jarvis" / "adapters" / "validation" / "_command.py"
    coding_loop = SRC_ROOT / "jarvis" / "application" / "coding" / "loop.py"

    violations = _references_identifier_outside_allowed_modules(
        SRC_ROOT / "jarvis",
        _BANNED_IDENTIFIER,
        frozenset({validation_command, coding_loop}),
    )

    assert violations == []
