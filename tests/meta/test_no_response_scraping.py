"""Mechanical enforcement of ADR-0045: no Claude/ChatGPT capability may read window content.

``DesktopWindowPort.read_visible_text`` is a real, legitimate method
(Terminal's own output-capture need, WP-52) -- but this project's
Claude/ChatGPT desktop-app capabilities must never call it (ADR-0045:
"No capability registered for either app may call
DesktopWindowPort.read_visible_text"). The restriction is enforced by
*which module* a call lives in, not a per-app exception embedded in
shared code: every "simple" desktop-control capability (Spotify,
Brave, VS Code, the Claude app, the ChatGPT app) composes in
``kernel/desktop.py``; Terminal's own multi-step flow (WP-52) is
structurally separate, in ``application/desktop/``. This test AST-scans
``kernel/desktop.py``'s real code (not docstrings, which legitimately
discuss ``read_visible_text`` in prose) for any reference to the
identifier at all -- if it ever appears there, something in the
Claude/ChatGPT/Brave/VS Code/Spotify composition roots is reading
window content, which ADR-0045 forbids unconditionally.

Deliberately AST-based, not a plain substring scan -- matching
``tests/meta/test_speaker_id_isolation.py``'s own precedent and its own
stated reason: a substring scan would false-positive on this very
module's docstrings, which correctly name ``read_visible_text`` in
prose to explain why it must not appear in real code.

Per this project's Meta-tests convention (CLAUDE.md), this structural
check also proves it actually fires against a real violation, not just
that today's tree happens to be clean.
"""

from __future__ import annotations

import ast
from pathlib import Path

KERNEL_DESKTOP = Path(__file__).resolve().parents[2] / "src/jarvis/kernel/desktop.py"

_BANNED_IDENTIFIER = "read_visible_text"


def _referenced_code_identifiers(source: str) -> set[str]:
    """Return every identifier referenced in actual code -- names, attributes, imports.

    Deliberately excludes docstrings and comments: those are string
    literals and stripped tokens to the AST, not ``ast.Name``/
    ``ast.Attribute``/``ast.ImportFrom`` nodes.
    """
    tree = ast.parse(source)
    identifiers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            identifiers.update(alias.asname or alias.name for alias in node.names)
    return identifiers


def test_kernel_desktop_never_references_read_visible_text() -> None:
    """kernel/desktop.py's real code never references read_visible_text -- ADR-0045's guarantee."""
    identifiers = _referenced_code_identifiers(KERNEL_DESKTOP.read_text(encoding="utf-8"))

    assert _BANNED_IDENTIFIER not in identifiers


def test_the_scan_predicate_actually_detects_a_violation() -> None:
    """The predicate genuinely fires on a real violation, not just passes on a clean tree."""
    violating_snippet = "def f(window):\n    return window.read_visible_text(1)\n"

    identifiers = _referenced_code_identifiers(violating_snippet)

    assert _BANNED_IDENTIFIER in identifiers


def test_the_scan_predicate_ignores_docstrings_that_merely_discuss_the_guarantee() -> None:
    """Prose explaining this restriction (naming the identifier) must not itself be a violation.

    This is the exact false-positive case a naive substring scan would
    hit -- and does hit, on this very module's own docstring, which
    correctly names "read_visible_text" in prose to document the rule.
    """
    documentation_only_snippet = (
        '"""This module must never call read_visible_text.\n'
        "\n"
        "See ADR-0045.\n"
        '"""\n'
        "\n"
        "SOME_CONSTANT = 1\n"
    )

    identifiers = _referenced_code_identifiers(documentation_only_snippet)

    assert _BANNED_IDENTIFIER not in identifiers
