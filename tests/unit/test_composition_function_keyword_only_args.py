"""Every real kernel composition function keeps its confirmation args keyword-only.

Real gap found by mutation testing (adapter-resilience/mutation-
extension/audit-log-integrity pass, Track 2, 2026-09-05): every
`authorize_and_*` composition function across `kernel/memory.py`,
`kernel/files.py`, `kernel/communications.py`, `kernel/desktop.py`, and
`kernel/coding.py` declares `physical_confirmation_available` (and
everything after it) keyword-only via a bare `*` separator -- but
nothing tested this. A mutant flipping that `*` to `/` (making the
preceding positional argument positional-*only* and everything after
it ordinary positional-or-keyword again) survived every existing test,
because no test calls any of these functions in a way that would
distinguish the two: every real call site in this codebase already
passes these arguments by keyword.

This is a real, if narrow, API-contract property, not a security
boundary in itself -- but it is the exact real thing the surviving
mutant proved untested, so it is proven here directly via
`inspect.signature()`, once, generically, across every real composition
function in all five modules, rather than writing one near-identical
hand-call test per function.
"""

from __future__ import annotations

import inspect

from jarvis.kernel import coding, communications, desktop, files, memory

_MODULES = (memory, files, communications, desktop, coding)


def _real_composition_functions() -> list[tuple[str, str, inspect.Signature]]:
    """Every real `authorize_and_*` function across the five target modules, with its signature."""
    found = []
    for module in _MODULES:
        for name, obj in vars(module).items():
            if name.startswith("authorize_and_") and callable(obj):
                found.append((module.__name__, name, inspect.signature(obj)))
    return found


def test_every_composition_function_exists_and_was_actually_found() -> None:
    """A real sanity check on the discovery mechanism itself, not just its output.

    If this drops to 0 (e.g. a future refactor renames the
    `authorize_and_*` convention), the test below would trivially and
    silently pass over nothing -- this guards against that.
    """
    functions = _real_composition_functions()
    assert len(functions) >= 25  # noqa: PLR2004 -- the real, current count is 26


def test_every_composition_function_keeps_confirmation_arguments_keyword_only() -> None:
    """The real regression proof: physical_confirmation_available is KEYWORD_ONLY everywhere.

    Directly kills the real `*` -> `/` mutant this pass's own mutation
    run found surviving in kernel/memory.py, kernel/files.py, and
    kernel/communications.py (kernel/desktop.py and kernel/coding.py
    checked too, for the same real property, not assumed safe by
    association).
    """
    functions = _real_composition_functions()
    checked = 0
    for module_name, function_name, signature in functions:
        if "physical_confirmation_available" not in signature.parameters:
            continue
        checked += 1
        parameter = signature.parameters["physical_confirmation_available"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, (
            f"{module_name}.{function_name}'s physical_confirmation_available is "
            f"{parameter.kind.name}, not KEYWORD_ONLY"
        )
        remote_parameter = signature.parameters["remote_confirmation_available"]
        assert remote_parameter.kind is inspect.Parameter.KEYWORD_ONLY, (
            f"{module_name}.{function_name}'s remote_confirmation_available is "
            f"{remote_parameter.kind.name}, not KEYWORD_ONLY"
        )
    assert checked >= 25  # noqa: PLR2004 -- every real composition function has both parameters
