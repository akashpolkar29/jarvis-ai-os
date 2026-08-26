"""Mechanical enforcement of ADR-0049's own amendment: the single memory-write path guarantee.

ADR-0049 grants ``Effect.MEMORY_WRITE`` an unconditional ``Tier.DENY``
floor for ``Classification.SECRET`` values -- but that guarantee only
holds if ``memory_effect_for()``/``MemoryWriteAuthorizer`` is genuinely
the *only* code path that ever reaches the real memory-write adapter's
write operation. As the ADR's own Consequences section states: "nothing
stops a future adapter, migration script, or debug tool from
constructing the real memory adapter directly and writing to it
through a path that never touches ``memory_effect_for()`` at all." The
required fix, named explicitly in that ADR and in
``m4-memory-retrieval.md``'s own WP-58 sketch, mirrors
``tests/meta/test_no_response_scraping.py``'s technique, inverted:
AST-scan every module under ``src/jarvis`` *except* ``kernel/memory.py``
and the real adapter's own defining module, asserting the adapter's
concrete class is never referenced there.

**Real, explicit sequencing note -- not a silent gap**: this test
module was first written in WP-58, *before* WP-61 (which is where the
real vector-store adapter and ``kernel/memory.py`` are actually built,
per ``m4-memory-retrieval.md``'s own WP ordering: "the safety-critical
piece lands first, not last"). At that point there was no real adapter
class in the tree yet for the concrete, real-tree assertion to bind
to -- exactly what the design doc's own phrase for WP-58 meant by
"gate-verified against fakes": the detection mechanism itself
(:func:`_references_identifier_outside_allowed_modules`) was built and
proven correct then, against synthetic fixtures, the same "predicate
detects a real violation" / "predicate ignores docstrings" proof
``test_no_response_scraping.py`` and ``test_speaker_id_isolation.py``
already established as this project's own precedent for a structural
guarantee.

**Now real, added in WP-61, completed in WP-63**:
:func:`test_no_module_under_src_references_sqlite_memory_adapter_outside_its_own_module`
is the concrete assertion the WP-58 sequencing note tracked --
``jarvis.adapters.memory.SqliteMemoryAdapter`` is the real adapter
class ADR-0049's own guarantee protects. ``kernel/memory.py`` (WP-63)
is now the real composition root that legitimately constructs it as
the single write path, and is the second, final entry in this
assertion's own allowlist -- the small, tracked, mechanical addition
this note itself predicted.
"""

from __future__ import annotations

from pathlib import Path

from tests.meta.helpers import iter_py_files, referenced_code_identifiers

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"


def _references_identifier_outside_allowed_modules(
    src_root: Path, banned_identifier: str, allowed_modules: frozenset[Path]
) -> list[Path]:
    """Return files under ``src_root``, outside ``allowed_modules``, referencing the identifier.

    ``allowed_modules`` are the only files permitted to reference the
    identifier in real code -- the composition root that owns the
    single write path, and the adapter's own defining module (which
    must obviously reference its own class).
    """
    return [
        py_file
        for py_file in iter_py_files(src_root)
        if py_file not in allowed_modules
        and banned_identifier in referenced_code_identifiers(py_file.read_text(encoding="utf-8"))
    ]


def test_the_scan_predicate_actually_detects_a_violation() -> None:
    """The predicate genuinely fires on a real violation, not just passes on a clean tree."""
    violating_snippet = (
        "from jarvis.adapters.memory_store import RealVectorStoreAdapter\n"
        "\n"
        "def bypass() -> RealVectorStoreAdapter:\n"
        "    return RealVectorStoreAdapter()\n"
    )

    identifiers = referenced_code_identifiers(violating_snippet)

    assert "RealVectorStoreAdapter" in identifiers


def test_the_scan_predicate_ignores_docstrings_that_merely_discuss_the_guarantee() -> None:
    """Prose explaining this restriction (naming the class) must not itself be a violation.

    This is the exact false-positive case a naive substring scan would
    hit -- and does hit, on this very module's own docstring, which
    correctly names the future adapter class in prose to document the
    rule it will enforce.
    """
    documentation_only_snippet = (
        '"""This module must never construct RealVectorStoreAdapter directly.\n'
        "\n"
        "See ADR-0049.\n"
        '"""\n'
        "\n"
        "SOME_CONSTANT = 1\n"
    )

    identifiers = referenced_code_identifiers(documentation_only_snippet)

    assert "RealVectorStoreAdapter" not in identifiers


def test_no_module_under_src_references_sqlite_memory_adapter_outside_its_own_module() -> None:
    """The real ADR-0049 guarantee: SqliteMemoryAdapter is referenced only where it must be.

    ``kernel/memory.py`` (WP-63) is the composition root that
    legitimately constructs ``SqliteMemoryAdapter`` as the single real
    write path -- exactly the exception this module's own docstring
    tracked in advance. No other module may reference it.
    """
    own_module = SRC_ROOT / "jarvis" / "adapters" / "memory.py"
    kernel_composition_root = SRC_ROOT / "jarvis" / "kernel" / "memory.py"

    violations = _references_identifier_outside_allowed_modules(
        SRC_ROOT / "jarvis",
        "SqliteMemoryAdapter",
        frozenset({own_module, kernel_composition_root}),
    )

    assert violations == []
