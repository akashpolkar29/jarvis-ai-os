"""Mechanical enforcement of ADR-0046's acceptance criterion #4: sandboxed launch only.

"No code path in this milestone's Terminal capability can inject text
into a terminal emulator window that SandboxPort did not itself
launch" -- checked structurally against the real source of
``jarvis.application.desktop.terminal``, not merely documented. ADR-0047
(WP-56) replaced this function's typing mechanism
(``DesktopWindowPort.type_text`` -> ``SyntheticInputPort.send_keysym``,
per that ADR's own reasoning: VTE never exposed the ``EditableText``
interface ``type_text`` needs); the same structural guarantee still
applies to whichever call actually types, so this file's checks were
updated to target ``send_keysym``, not weakened or dropped:

1. :func:`test_launch_precedes_send_keysym_in_run_in_sandboxed_terminal`
   -- within ``run_in_sandboxed_terminal``'s own flat statement list, a
   call naming ``launch`` appears at an earlier statement index than
   any call naming ``send_keysym``. Deliberately restricted to the
   function's *top-level* statements (not walking into nested blocks
   -- ``ast.walk`` on each top-level statement still finds calls nested
   inside that statement's own body, e.g. inside the per-character
   ``for`` loop, so this remains a real, meaningful proof without
   needing to reason about control flow across conditionals to be
   correct.

2. :func:`test_find_or_launch_is_never_called_with_a_launch_command`
   -- no call to ``find_or_launch`` anywhere in the module passes a
   second argument (positional or the ``launch_command`` keyword).
   ``DesktopWindowPort.find_or_launch``'s own launch path
   (``adapters/desktop_window.py``'s ``_launch_subprocess``) is a
   plain, unsandboxed subprocess call -- reaching it from this module,
   even as a well-intentioned retry fallback, would silently defeat
   the whole sandboxed-launch-only guarantee this ADR requires.

Per this project's Meta-tests convention (CLAUDE.md), both checks also
prove they actually fire against a deliberate violation, not just that
today's tree happens to be clean.
"""

from __future__ import annotations

import ast
from pathlib import Path

TERMINAL_MODULE = Path(__file__).resolve().parents[2] / "src/jarvis/application/desktop/terminal.py"


def _call_name(node: ast.Call) -> str | None:
    """Return a Call node's function name, whether it's a bare name or an attribute access."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _top_level_call_statement_indices(
    func: ast.FunctionDef | ast.AsyncFunctionDef, call_name: str
) -> list[int]:
    """Return the statement indices (within func's flat body) of calls named call_name.

    Only inspects func's own top-level statements, not nested blocks --
    see the module docstring for why that's the right scope here.
    """
    indices = []
    for i, stmt in enumerate(func.body):
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call) and _call_name(node) == call_name:
                indices.append(i)
                break
    return indices


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Find a top-level function by name -- run_in_sandboxed_terminal is async (ADR-0047)."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    msg = f"No function named {name!r} found."
    raise AssertionError(msg)


def _launch_precedes_send_keysym(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return whether every send_keysym call statement comes after some launch call statement."""
    launch_indices = _top_level_call_statement_indices(func, "launch")
    send_keysym_indices = _top_level_call_statement_indices(func, "send_keysym")
    if not launch_indices or not send_keysym_indices:
        return False
    return min(launch_indices) < min(send_keysym_indices)


def test_launch_precedes_send_keysym_in_run_in_sandboxed_terminal() -> None:
    """sandbox.launch() is always called before synthetic_input.send_keysym(), structurally."""
    tree = ast.parse(TERMINAL_MODULE.read_text(encoding="utf-8"))
    func = _find_function(tree, "run_in_sandboxed_terminal")

    assert _launch_precedes_send_keysym(func) is True


def test_the_ordering_predicate_actually_detects_a_violation() -> None:
    """The predicate genuinely fires when send_keysym precedes launch, not just on a clean tree."""
    violating_source = (
        "def f(sandbox, synthetic_input):\n"
        "    synthetic_input.send_keysym(1, 1, press=True)\n"
        "    sandbox.launch(('a',))\n"
    )
    tree = ast.parse(violating_source)
    func = _find_function(tree, "f")

    assert _launch_precedes_send_keysym(func) is False


def test_the_ordering_predicate_does_not_fire_when_send_keysym_is_never_called() -> None:
    """A function with no send_keysym call at all is not a false violation."""
    clean_source = "def f(sandbox):\n    sandbox.launch(('a',))\n"
    tree = ast.parse(clean_source)
    func = _find_function(tree, "f")

    assert _launch_precedes_send_keysym(func) is False


def _find_or_launch_call_argument_counts(tree: ast.Module) -> list[int]:
    """Return the total (positional + keyword) argument count of every find_or_launch call."""
    counts = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node) == "find_or_launch":
            counts.append(len(node.args) + len(node.keywords))
    return counts


def test_find_or_launch_is_never_called_with_a_launch_command() -> None:
    """Every find_or_launch call in this module passes exactly one argument: app_id, no more."""
    tree = ast.parse(TERMINAL_MODULE.read_text(encoding="utf-8"))

    counts = _find_or_launch_call_argument_counts(tree)

    assert counts != []
    assert all(count == 1 for count in counts)


def test_the_argument_count_predicate_actually_detects_a_violation() -> None:
    """The predicate genuinely fires on a real violation (a second argument), not just passes."""
    violating_source = (
        "def f(window):\n    window.find_or_launch('gnome-terminal', ('gnome-terminal',))\n"
    )
    tree = ast.parse(violating_source)

    counts = _find_or_launch_call_argument_counts(tree)

    assert counts == [2]
