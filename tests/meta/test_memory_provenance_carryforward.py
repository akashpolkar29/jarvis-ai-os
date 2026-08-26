"""Mechanical enforcement of ADR-0050: a MemoryRecord's real provenance is never discarded.

ADR-0050's own load-bearing rule: "no adapter or application-layer
code ... may construct a fresh, unclassified ``Provenance`` for a value
that originated from a ``MemoryRecord``." Left as convention alone,
nothing stops a future caller from unwrapping a recalled record's
inner value and re-wrapping it with ``Provenance.user()`` (or any other
fresh-construction path), silently discarding the real classification
this whole milestone's write-time gating (ADR-0049) depends on
surviving into re-use.

Two independent checks, mirroring
``tests/meta/test_speaker_id_isolation.py``'s own two-layer technique
exactly:

1. :func:`test_memory_record_value_is_still_a_tainted_object` -- pins
   ``MemoryRecord.value``'s own type annotation to ``Tainted[object]``.
   Provenance is carried in the *type itself*, not bolted on
   separately -- if this field's annotation ever changed to a bare
   ``object``, there would be no provenance left on a retrieved
   record for any caller to carry forward at all, no matter how
   careful the calling code was. Forces a deliberate look here if
   anyone ever changes it.

2. :func:`test_no_module_under_src_references_both_memory_record_and_provenance`
   -- even with (1) holding, a caller could still read
   ``record.value.value`` (the raw wrapped value, discarding
   ``record.value.provenance``) and construct a *new* ``Tainted``
   around a fresh ``Provenance.user()``/``Provenance.system()``/bare
   ``Provenance(...)``. This test AST-scans every real, non-barrel
   module under ``src/jarvis`` for the combination itself: no file may
   *reference in code* (not a docstring or comment merely discussing
   the guarantee) both ``MemoryRecord`` and ``Provenance``. The safe,
   encouraged pattern -- reading an existing record's own
   ``.provenance`` attribute to carry it forward -- never touches the
   ``Provenance`` class name at all, so it is not, and should not be,
   flagged by this scan. ``__init__.py`` barrels are excluded, matching
   ``test_speaker_id_isolation.py``'s own reasoning: a package's
   re-export barrel legitimately names everything in its package
   together, which is aggregation, not construction.

**Two further, explicit, justified exceptions**:

- ``jarvis.adapters.memory`` (``SqliteMemoryAdapter``, WP-61)
  legitimately references both markers -- it is the real persistence
  boundary, and its own deserialization path
  (``_row_to_record_and_embedding``) *reconstructs* a ``MemoryRecord``'s
  exact original ``Provenance`` from that same record's own
  previously-persisted ``trust``/``classification``/``sources``
  columns. This is not the violation ADR-0050 names: it is not
  discarding a real classification for a fresh, unclassified one
  (``Provenance.user()``/``.system()``); it is faithfully rebuilding
  the one that was already there, the same serialize/deserialize
  round-trip every persistence adapter must do for its own domain type.
- ``jarvis.kernel.memory`` (WP-63) references ``MemoryRecord`` only in
  a return-type annotation (``MemoryRecallOutcome.records``) and
  constructs ``Provenance.user()`` only for a freshly-typed/spoken
  argument (the text to memorize, or the query string) -- the same
  "wrap direct user input" pattern ``ping``/music commands/
  ``fs.read_file``'s own path argument already use. It never unwraps
  an existing ``MemoryRecord``'s value and re-wraps it with a fresh
  ``Provenance`` -- the actual violation this test exists to catch.

Named here explicitly, as their own allowlist entries, rather than
silently narrowing the general rule.

Deliberately AST-based, not a substring scan -- this very module's own
docstring names both terms in prose to explain the rule, which a
substring scan would incorrectly flag.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path

from jarvis.domain.memory import MemoryRecord
from jarvis.domain.provenance import Provenance, Tainted
from tests.meta.helpers import iter_py_files, referenced_code_identifiers

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"

_MEMORY_RECORD_MARKERS = frozenset({"MemoryRecord"})
_FRESH_PROVENANCE_MARKERS = frozenset({"Provenance"})


def _references_both_memory_record_and_provenance(source: str) -> bool:
    """Return whether ``source``'s real code (not docstrings) mentions both vocabularies."""
    identifiers = referenced_code_identifiers(source)
    return bool(identifiers & _MEMORY_RECORD_MARKERS) and bool(
        identifiers & _FRESH_PROVENANCE_MARKERS
    )


def test_memory_record_value_is_still_a_tainted_object() -> None:
    """MemoryRecord.value's own type annotation is still Tainted[object] -- provenance-carrying."""
    fields = {field.name: field.type for field in dataclasses.fields(MemoryRecord)}

    assert fields["value"] == "Tainted[object]"


def test_memory_record_value_really_is_a_tainted_instance_at_runtime() -> None:
    """A real MemoryRecord's .value is a real Tainted, whose .provenance is the one carried."""
    record = MemoryRecord(
        identifier="mem:1",
        value=Tainted.user("prefers tabs"),
        written_at=datetime(2026, 1, 1, tzinfo=UTC),
        expires_at=None,
    )

    assert isinstance(record.value, Tainted)
    assert record.value.provenance == Provenance.user()


_ALLOWED_RECONSTRUCTION_MODULES = frozenset(
    {
        SRC_ROOT / "jarvis" / "adapters" / "memory.py",
        SRC_ROOT / "jarvis" / "kernel" / "memory.py",
    }
)


def test_no_module_under_src_references_both_memory_record_and_provenance() -> None:
    """No real source file's actual code mixes MemoryRecord-related code with fresh Provenance.

    See the module docstring for the full reasoning -- this is the
    real mechanical enforcement of ADR-0050's own carry-forward rule.
    __init__.py files are excluded (aggregation, not construction);
    ``adapters/memory.py`` and ``kernel/memory.py`` are excluded too
    (real, justified exceptions -- see the module docstring's own).
    """
    violations = [
        py_file
        for py_file in iter_py_files(SRC_ROOT / "jarvis")
        if py_file.name != "__init__.py"
        and py_file not in _ALLOWED_RECONSTRUCTION_MODULES
        and _references_both_memory_record_and_provenance(py_file.read_text(encoding="utf-8"))
    ]

    assert violations == [], (
        f"{[str(f) for f in violations]} reference both MemoryRecord and Provenance in actual "
        "code -- a recalled record's own provenance must be carried forward unmodified, never "
        "discarded for a fresh, unclassified one (ADR-0050)."
    )


def test_the_scan_predicate_actually_detects_a_violation() -> None:
    """The predicate genuinely fires on a real violation, not just passes on a clean tree."""
    violating_snippet = (
        "from jarvis.domain.memory import MemoryRecord\n"
        "from jarvis.domain.provenance import Provenance, Tainted\n"
        "\n"
        "def rewrap(record: MemoryRecord) -> Tainted[object]:\n"
        "    return Tainted(record.value.value, Provenance.user())\n"
    )

    assert _references_both_memory_record_and_provenance(violating_snippet) is True


def test_the_scan_predicate_does_not_fire_on_memory_record_only_code() -> None:
    """A file that only references MemoryRecord, with no Provenance mention, is not flagged.

    This is exactly the safe, encouraged pattern: reading an existing
    record's own .provenance attribute never names the class itself.
    """
    safe_snippet = (
        "from jarvis.domain.memory import MemoryRecord\n"
        "from jarvis.domain.provenance import Classification\n"
        "\n"
        "def is_secret(record: MemoryRecord) -> bool:\n"
        "    return record.value.provenance.classification is Classification.SECRET\n"
    )

    assert _references_both_memory_record_and_provenance(safe_snippet) is False


def test_the_scan_predicate_does_not_fire_on_provenance_only_code() -> None:
    """A file that only references Provenance, with no MemoryRecord mention, is not flagged."""
    provenance_only_snippet = (
        "from jarvis.domain.provenance import Provenance\n"
        "\n"
        "def fresh() -> Provenance:\n"
        "    return Provenance.user()\n"
    )

    assert _references_both_memory_record_and_provenance(provenance_only_snippet) is False


def test_the_scan_predicate_ignores_docstrings_that_merely_discuss_the_guarantee() -> None:
    """Prose explaining this rule (naming both terms) must not itself be a violation.

    This is the exact false-positive case a naive substring scan would
    hit -- and does hit, on this very module's own docstring.
    """
    documentation_only_snippet = (
        '"""A MemoryRecord\'s value must never be rewrapped with a fresh Provenance.\n'
        "\n"
        "See ADR-0050.\n"
        '"""\n'
        "\n"
        "SOME_CONSTANT = 1\n"
    )

    assert _references_both_memory_record_and_provenance(documentation_only_snippet) is False
