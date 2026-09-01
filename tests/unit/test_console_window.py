"""Unit tests for jarvis.ui.console.window.

`_build_console_argv` is pure -- tested directly, no subprocess
involved, mirroring `adapters/sandbox.py`'s own `_build_bwrap_argv`
precedent. `show_console_line`'s own real launch (a real, detached
GTK4 subprocess) is exercised via an injected fake `launch` function,
never a real subprocess -- the real path needs a real display, matching
`jarvis.ui.confirm.dialog.show_confirmation_dialog`'s own "proven by
manual verification, not the automated suite" precedent.
"""

from __future__ import annotations

import sys

from jarvis.ui.console.window import _build_console_argv, show_console_line


def test_build_console_argv_uses_the_running_interpreter() -> None:
    argv = _build_console_argv("hello", 4.0)

    assert argv[0] == sys.executable
    assert argv[1] == "-c"


def test_build_console_argv_passes_text_as_a_real_argument_not_interpolated() -> None:
    """text reaches the subprocess as argv[3], never formatted into the script's own source."""
    argv = _build_console_argv("browser.open_page: https://example.com", 4.0)

    assert argv[3] == "browser.open_page: https://example.com"
    assert "https://example.com" not in argv[2]  # never interpolated into the script body


def test_build_console_argv_passes_timeout_as_a_real_string_argument() -> None:
    argv = _build_console_argv("hello", 7.5)

    assert argv[4] == "7.5"


def test_build_console_argv_is_stable_for_the_same_inputs() -> None:
    """Pure function: same inputs, same real argv, every time."""
    first = _build_console_argv("hello", 4.0)
    second = _build_console_argv("hello", 4.0)

    assert first == second


def test_show_console_line_launches_the_real_built_argv() -> None:
    launched: list[tuple[str, ...]] = []

    show_console_line("hello", timeout_s=4.0, launch=launched.append)

    assert len(launched) == 1
    assert launched[0] == _build_console_argv("hello", 4.0)


def test_show_console_line_uses_the_default_timeout_when_not_given() -> None:
    launched: list[tuple[str, ...]] = []

    show_console_line("hello", launch=launched.append)

    assert launched[0][4] == "4.0"
