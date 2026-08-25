"""Mechanical enforcement of ADR-0012: speaker verification can never become authorization.

ADR-0012 says voice/speaker verification is a convenience filter, never
an authorization boundary. Two independent checks make this a real,
enforced guarantee rather than a comment someone could quietly work
around:

1. :func:`test_policy_context_has_no_speaker_related_field` --
   :class:`~jarvis.domain.policy.PolicyContext` (the only value
   :func:`~jarvis.domain.policy.evaluate` ever reads to make a
   Decision) has exactly two boolean fields today. If anyone ever adds
   a third field, this test forces them to look at it here, once,
   deliberately -- silent field additions can't sail through.

2. :func:`test_no_module_under_src_references_both_policy_context_and_speaker_id`
   -- even with (1) holding, someone could still compute one of those
   *existing* booleans (``physical_confirmation_available``, say) from
   a :class:`~jarvis.domain.speaker_id.SpeakerScore` at the call site
   (e.g. a ``ConfirmationPort`` adapter secretly wired up to accept
   "the speaker matched" as "physically present"). That wouldn't touch
   PolicyContext's shape, so (1) alone can't catch it. This test
   AST-scans every real, non-``__init__.py`` source file for the
   combination itself: no file under ``src/jarvis`` may *reference in
   code* (an import, a call, an attribute access -- not a docstring or
   comment discussing the guarantee, which several of this project's
   own files legitimately do) both PolicyContext-related identifiers
   and SpeakerScore/SpeakerIdPort-related identifiers.
   ``__init__.py`` files are excluded deliberately: every package's
   ``__init__.py`` in this codebase is a pure re-export barrel that
   legitimately names everything in its package together (including,
   e.g., ``domain/__init__.py`` re-exporting both ``PolicyContext``
   and ``SpeakerScore`` alongside every other domain type) -- that is
   aggregation, not construction, and is not the violation this test
   exists to catch. Forcing those two vocabularies to stay
   module-disjoint in real, non-barrel code is the mechanical
   guarantee -- the two concepts structurally cannot meet where actual
   construction/wiring logic lives.

   Deliberately AST-based, not a plain substring scan: a substring
   scan would false-positive on this very port/adapter pair's own
   docstrings, which correctly name "PolicyContext" in prose to
   *explain* this isolation rule. Only real ``ast.Name``/``ast.
   Attribute``/``ast.ImportFrom`` references count; docstrings and
   comments are just string/token content to the parser, invisible to
   this scan, which is exactly the distinction that matters here.

Per this project's Meta-tests convention (CLAUDE.md), a structural
check like this needs its own proof that it actually fires against a
real violation, not just that today's tree happens to be clean:
:func:`test_the_scan_predicate_actually_detects_a_violation` runs the
identical predicate against a deliberately-crafted violating snippet.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from jarvis.domain.policy import PolicyContext
from tests.meta.helpers import iter_py_files, referenced_code_identifiers

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"

_POLICY_MARKERS = frozenset({"PolicyContext", "get_current_context"})
_SPEAKER_MARKERS = frozenset({"SpeakerScore", "SpeakerIdPort"})


def _references_both_policy_and_speaker_id(source: str) -> bool:
    """Return whether ``source``'s real code (not docstrings) mentions both vocabularies."""
    identifiers = referenced_code_identifiers(source)
    return bool(identifiers & _POLICY_MARKERS) and bool(identifiers & _SPEAKER_MARKERS)


def test_policy_context_has_no_speaker_related_field() -> None:
    """PolicyContext's only fields are the two known-safe booleans -- no SpeakerScore field."""
    fields = dataclasses.fields(PolicyContext)
    field_names = {field.name for field in fields}

    assert field_names == {"physical_confirmation_available", "remote_confirmation_available"}
    for field in fields:
        assert field.type == "bool", f"PolicyContext.{field.name} is not bool: {field.type!r}"


def test_no_module_under_src_references_both_policy_context_and_speaker_id() -> None:
    """No real source file's actual code mixes PolicyContext-related code with speaker-id code.

    This is the actual mechanical enforcement described in the module
    docstring: the two vocabularies are forced to stay disjoint in
    real code across every non-barrel file under src/jarvis, not just
    within PolicyContext's own field list. __init__.py files are
    excluded -- see the module docstring for why they're a legitimate,
    different case (aggregation, not construction).
    """
    violations = [
        py_file
        for py_file in iter_py_files(SRC_ROOT)
        if py_file.name != "__init__.py"
        and _references_both_policy_and_speaker_id(py_file.read_text(encoding="utf-8"))
    ]

    assert violations == [], (
        f"{[str(f) for f in violations]} reference both PolicyContext-related code and "
        "SpeakerScore/SpeakerIdPort in actual code -- speaker verification must never "
        "become an authorization input (ADR-0012)."
    )


def test_the_scan_predicate_actually_detects_a_violation() -> None:
    """The scanning predicate genuinely fires on a real violation, not just passes on a clean tree.

    Proves test_no_module_under_src_references_both_policy_context_and_speaker_id
    isn't vacuously true -- the check mechanism itself works.
    """
    violating_snippet = (
        "from jarvis.domain.policy import PolicyContext\n"
        "from jarvis.domain.speaker_id import SpeakerScore\n"
        "\n"
        "def build_context(score: SpeakerScore) -> PolicyContext:\n"
        "    return PolicyContext(\n"
        "        physical_confirmation_available=score.verified,\n"
        "        remote_confirmation_available=False,\n"
        "    )\n"
    )

    assert _references_both_policy_and_speaker_id(violating_snippet) is True


def test_the_scan_predicate_does_not_fire_on_policy_only_code() -> None:
    """A file that only references PolicyContext, with no speaker-id mention, is not flagged."""
    policy_only_snippet = (
        "from jarvis.domain.policy import PolicyContext\n"
        "\n"
        "def build_context() -> PolicyContext:\n"
        "    return PolicyContext(\n"
        "        physical_confirmation_available=True,\n"
        "        remote_confirmation_available=False,\n"
        "    )\n"
    )

    assert _references_both_policy_and_speaker_id(policy_only_snippet) is False


def test_the_scan_predicate_does_not_fire_on_speaker_id_only_code() -> None:
    """A file that only references SpeakerScore, with no PolicyContext mention, is not flagged."""
    speaker_only_snippet = (
        "from jarvis.domain.speaker_id import SpeakerScore\n"
        "\n"
        "def unverified() -> SpeakerScore:\n"
        "    return SpeakerScore(verified=False, confidence=0.0)\n"
    )

    assert _references_both_policy_and_speaker_id(speaker_only_snippet) is False


def test_the_scan_predicate_ignores_docstrings_that_merely_discuss_the_guarantee() -> None:
    """Prose explaining this isolation rule (naming both terms) must not itself be a violation.

    This is the exact false-positive case a naive substring scan would
    hit -- and does hit, on this project's own real
    ports/speaker_id.py and domain/speaker_id.py docstrings, which
    correctly name "PolicyContext" while documenting this guarantee.
    """
    documentation_only_snippet = (
        '"""This module\'s SpeakerScore must never reach PolicyContext construction.\n'
        "\n"
        "See ADR-0012: SpeakerIdPort output is audit/UX only.\n"
        '"""\n'
        "\n"
        "SOME_CONSTANT = 1\n"
    )

    assert _references_both_policy_and_speaker_id(documentation_only_snippet) is False
