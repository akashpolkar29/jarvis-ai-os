"""Mechanical enforcement: M6a's real code has no send/create-event write path, structurally.

ADR-0057 remains `Proposed`, not `Accepted` -- unreviewed by the user
directly. `EmailPort.send_message`/`CalendarPort.create_event` exist
on their own Protocols (for `EmailPort`'s/`CalendarPort`'s own
conceptual completeness), but every real adapter's own implementation
raises `NotImplementedError` unconditionally, before any real network
call. This is that boundary's own real, mechanical proof -- mirroring
`tests/meta/test_job_assistance_no_submission.py`'s own established
"prove the boundary, don't just assert it in prose" discipline,
applied here to the send/invite gap this pass deliberately leaves
open.

Two real, separate assertions:

1. **No raw SMTP client, and no real CalDAV event-creation method,
   anywhere in real code under M6a's own scope**
   (`ports/email.py`, `ports/calendar.py`, `adapters/email.py`,
   `adapters/calendar.py`, `kernel/communications.py`). The CalDAV
   method names banned here are not hypothetical -- confirmed directly
   against the installed `caldav` 3.2.1 package's own real
   `Calendar` class (`add_event`, `save_event`, `save_with_invites`,
   `save_object`, `add_object` all genuinely exist on it today).
   `save` alone is deliberately **not** banned -- it is already a real,
   legitimate identifier in this exact scope
   (`JsonFileAuditStorageAdapter.storage.save(chain)`, used in every
   real composition function in `kernel/communications.py`); banning
   it would be a real false positive on already-correct code, not a
   safety improvement.
2. **`send_message`/`create_event`'s own real implementations each
   contain an unconditional, top-level `raise NotImplementedError`** --
   an AST-structural check that this is not merely true today by
   inspection, but genuinely unconditional (not buried inside an `if`
   that could someday be made `False`).

Per this project's own Meta-tests convention (`CLAUDE.md`), every
predicate below also proves it actually fires against a deliberate
violation, and that it does not false-positive on legitimate code.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from tests.meta.helpers import SRC_ROOT, referenced_code_identifiers

if TYPE_CHECKING:
    from pathlib import Path

_SCOPE = (
    SRC_ROOT / "jarvis" / "ports" / "email.py",
    SRC_ROOT / "jarvis" / "ports" / "calendar.py",
    SRC_ROOT / "jarvis" / "adapters" / "email.py",
    SRC_ROOT / "jarvis" / "adapters" / "calendar.py",
    SRC_ROOT / "jarvis" / "kernel" / "communications.py",
)

_BANNED_IDENTIFIERS = frozenset(
    {
        # A raw SMTP client -- imaplib (reading) is fine and expected;
        # smtplib (sending) must never appear.
        "smtplib",
        # Real, confirmed-current write-shaped methods on caldav's own
        # Calendar class (3.2.1) -- not hypothetical, checked directly.
        "add_event",
        "save_event",
        "save_with_invites",
        "save_object",
        "add_object",
    }
)


def _scope_paths() -> list[Path]:
    return [path for path in _SCOPE if path.exists()]


def _find_function(tree: ast.Module, name: str) -> ast.AsyncFunctionDef | ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef) and node.name == name:
            return node
    msg = f"No function named {name!r} found."
    raise AssertionError(msg)


def _has_unconditional_top_level_raise_not_implemented(
    func: ast.AsyncFunctionDef | ast.FunctionDef,
) -> bool:
    """Return whether func's own top-level body contains an unconditional NotImplementedError raise."""  # noqa: E501
    for stmt in func.body:
        if not isinstance(stmt, ast.Raise) or stmt.exc is None:
            continue
        call = stmt.exc
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
            if call.func.id == "NotImplementedError":
                return True
        elif isinstance(call, ast.Name) and call.id == "NotImplementedError":
            return True
    return False


def test_no_m6a_module_references_a_banned_send_or_create_identifier() -> None:
    """No real code under M6a's own scope references smtplib or a real CalDAV write method."""
    for path in _scope_paths():
        identifiers = referenced_code_identifiers(path.read_text(encoding="utf-8"))
        found = identifiers & _BANNED_IDENTIFIERS
        assert not found, f"{path} references banned identifier(s): {found}"


def test_email_send_message_unconditionally_raises_not_implemented() -> None:
    tree = ast.parse((SRC_ROOT / "jarvis" / "adapters" / "email.py").read_text(encoding="utf-8"))
    func = _find_function(tree, "send_message")

    assert _has_unconditional_top_level_raise_not_implemented(func) is True


def test_calendar_create_event_unconditionally_raises_not_implemented() -> None:
    tree = ast.parse((SRC_ROOT / "jarvis" / "adapters" / "calendar.py").read_text(encoding="utf-8"))
    func = _find_function(tree, "create_event")

    assert _has_unconditional_top_level_raise_not_implemented(func) is True


def test_the_identifier_ban_actually_detects_a_real_smtp_send_violation() -> None:
    """The predicate genuinely fires on a real violation, not just on a clean tree."""
    violating_snippet = (
        "import smtplib\n\n"
        "def f(host, msg):\n"
        "    with smtplib.SMTP(host) as s:\n"
        "        s.send_message(msg)\n"
    )

    identifiers = referenced_code_identifiers(violating_snippet)

    assert "smtplib" in identifiers & _BANNED_IDENTIFIERS


def test_the_identifier_ban_actually_detects_a_real_caldav_write_violation() -> None:
    """The predicate fires on a real caldav Calendar.save_event() call."""
    violating_snippet = "def f(calendar, ical_text):\n    calendar.save_event(ical_text)\n"

    identifiers = referenced_code_identifiers(violating_snippet)

    assert "save_event" in identifiers & _BANNED_IDENTIFIERS


def test_the_identifier_ban_does_not_false_positive_on_the_real_audit_storage_save_call() -> None:
    """storage.save(chain) -- a real, legitimate, unrelated call in this exact scope -- is never flagged."""  # noqa: E501
    legitimate_snippet = (
        "def f(storage, chain):\n    storage.save(chain)\n    return storage.load()\n"
    )

    identifiers = referenced_code_identifiers(legitimate_snippet)

    assert identifiers & _BANNED_IDENTIFIERS == set()


def test_the_raise_predicate_actually_detects_a_conditional_raise_as_insufficient() -> None:
    """Fires (returns False) when NotImplementedError is only conditionally raised."""
    violating_source = (
        "def f(x):\n"
        "    if x:\n"
        "        raise NotImplementedError('only sometimes')\n"
        "    return None\n"
    )
    tree = ast.parse(violating_source)
    func = _find_function(tree, "f")

    assert _has_unconditional_top_level_raise_not_implemented(func) is False


def test_the_raise_predicate_recognizes_a_real_unconditional_raise() -> None:
    clean_source = "def f(x):\n    del x\n    raise NotImplementedError('always')\n"
    tree = ast.parse(clean_source)
    func = _find_function(tree, "f")

    assert _has_unconditional_top_level_raise_not_implemented(func) is True
