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

**Real, explicit sequencing note -- not a silent gap**: WP-58 (this
work package) lands *before* WP-61, which is where the real vector-store
adapter and ``kernel/memory.py`` are actually built (per
``m4-memory-retrieval.md``'s own WP ordering: "the safety-critical
piece lands first, not last"). There is therefore no real adapter
class or ``kernel/memory.py`` module in the tree yet for the concrete,
real-tree assertion to bind to -- exactly what the design doc's own
phrase for this work package means by "gate-verified against fakes":
the detection mechanism itself (:func:`_references_identifier_outside_allowed_modules`)
is built and proven correct now, against synthetic fixtures, the same
"predicate detects a real violation" / "predicate ignores docstrings"
proof ``test_no_response_scraping.py`` and
``test_speaker_id_isolation.py`` already established as this project's
own precedent for a structural guarantee. The concrete, real-tree
assertion -- naming the real adapter's actual class and module -- is
added as a small, mechanical addition when WP-61 introduces that class,
not before; that addition is explicitly tracked, not left implicit.
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


def test_the_scan_predicate_excludes_allowed_modules_by_path() -> None:
    """A file listed in allowed_modules is never reported, even though it references the identifier.

    The real assertion (added in WP-61, once the adapter exists) will
    rely on this exclusion to let the adapter's own defining module
    and kernel/memory.py freely reference the concrete class -- this
    proves the exclusion mechanism itself works, independent of which
    real files are eventually named.
    """
    scratch_root = SRC_ROOT / "jarvis"
    allowed = scratch_root / "adapters" / "clock.py"
    violations = _references_identifier_outside_allowed_modules(
        scratch_root, "SystemClockAdapter", frozenset({allowed})
    )

    assert allowed not in violations
    assert violations == []


def test_no_module_under_src_references_system_clock_adapter_outside_its_own_module() -> None:
    """Sanity-checks the real scan end-to-end against an already-real, already-narrow example.

    ``SystemClockAdapter`` (``adapters/clock.py``) stands in here for
    the not-yet-built memory adapter: it is likewise a concrete class
    that only its own defining module (and, in its case, nothing
    else -- it's constructed only in tests/kernel composition, never
    referenced by name elsewhere in src/) should mention. This proves
    the real scan machinery -- not just synthetic fixtures -- correctly
    finds zero violations against real source today.
    """
    own_module = SRC_ROOT / "jarvis" / "adapters" / "clock.py"

    violations = _references_identifier_outside_allowed_modules(
        SRC_ROOT / "jarvis", "SystemClockAdapter", frozenset({own_module})
    )

    assert violations == []
