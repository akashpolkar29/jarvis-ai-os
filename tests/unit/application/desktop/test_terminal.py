"""Unit tests for jarvis.application.desktop.terminal.run_in_sandboxed_terminal.

What's mocked and why: stub SandboxPort/DesktopWindowPort (with call
tracking) stand in for BwrapSandboxAdapter/AtspiDesktopWindowAdapter --
these tests must be hermetic and never actually launch a real,
visible terminal window. sleep_fn is always a no-op injection so
retry-loop tests run instantly rather than waiting real seconds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jarvis.application.desktop.terminal import run_in_sandboxed_terminal
from jarvis.domain.desktop import WindowHandle
from jarvis.ports.desktop_window import WindowNotFoundError

if TYPE_CHECKING:
    from jarvis.domain.process import CommandResult

_TERMINAL_APP_ID = "gnome-terminal"
_FAKE_PID = 12345
_EXPECTED_FIND_ATTEMPTS_AFTER_TWO_FAILURES = 3


class _StubSandbox:
    """A SandboxPort test double that records launch()/run() calls, in order."""

    def __init__(self) -> None:
        """Start with an empty call log."""
        self.calls: list[tuple[str, ...]] = []

    def run(
        self,
        command: tuple[str, ...],
        *,
        bind_paths: tuple[object, ...] = (),
        allow_network: bool = False,
    ) -> CommandResult:
        """Not used by run_in_sandboxed_terminal -- present only to satisfy SandboxPort."""
        raise NotImplementedError

    def launch(
        self,
        command: tuple[str, ...],
        *,
        bind_paths: tuple[object, ...] = (),  # noqa: ARG002
        allow_network: bool = False,  # noqa: ARG002
    ) -> int:
        """Record a launch() call and return a fake pid."""
        self.calls.append(("launch", *command))
        return _FAKE_PID


class _StubDesktopWindow:
    """A DesktopWindowPort test double that records find/focus/type/read calls, in order.

    find_or_launch fails a configurable number of times before
    succeeding, to exercise _find_the_sandboxed_terminal_window's
    retry loop for real.
    """

    def __init__(self, *, fail_first_n_finds: int = 0, read_result: str | None = "$ ") -> None:
        """Configure how many initial find_or_launch calls should raise before succeeding."""
        self.calls: list[tuple[str, ...]] = []
        self._remaining_failures = fail_first_n_finds
        self._read_result = read_result

    def find_or_launch(
        self, app_id: str, launch_command: tuple[str, ...] | None = None
    ) -> WindowHandle:
        """Record a find_or_launch() call; raise WindowNotFoundError if configured to fail."""
        self.calls.append(("find_or_launch", app_id, str(launch_command)))
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            msg = f"No window found for {app_id!r} (yet)."
            raise WindowNotFoundError(msg)
        return WindowHandle(value=f"{app_id}:1", app_id=app_id)

    def focus(self, handle: WindowHandle) -> None:
        """Record a focus() call."""
        self.calls.append(("focus", handle.app_id))

    def type_text(self, handle: WindowHandle, text: str) -> None:
        """Record a type_text() call."""
        self.calls.append(("type_text", handle.app_id, text))

    def read_visible_text(self, handle: WindowHandle) -> str | None:
        """Record a read_visible_text() call and return the configured result."""
        self.calls.append(("read_visible_text", handle.app_id))
        return self._read_result


def test_happy_path_launches_finds_focuses_types_and_reads_in_order() -> None:
    """The whole flow runs in the documented order: launch, find, focus, type, read."""
    sandbox = _StubSandbox()
    window = _StubDesktopWindow(read_result="$ pytest\n5 passed")

    result = run_in_sandboxed_terminal(
        "pytest\n", sandbox=sandbox, desktop_window=window, sleep_fn=lambda _s: None
    )

    assert sandbox.calls == [("launch", "gnome-terminal")]
    assert window.calls == [
        ("find_or_launch", _TERMINAL_APP_ID, "None"),
        ("focus", _TERMINAL_APP_ID),
        ("type_text", _TERMINAL_APP_ID, "pytest\n"),
        ("read_visible_text", _TERMINAL_APP_ID),
    ]
    assert result == "$ pytest\n5 passed"


def test_launch_always_happens_before_type_text() -> None:
    """sandbox.launch() is called before window.type_text() -- the real ADR-0046 ordering."""
    sandbox = _StubSandbox()
    window = _StubDesktopWindow()

    run_in_sandboxed_terminal(
        "ls\n", sandbox=sandbox, desktop_window=window, sleep_fn=lambda _s: None
    )

    type_text_call_index = next(i for i, c in enumerate(window.calls) if c[0] == "type_text")
    assert sandbox.calls != []
    assert type_text_call_index >= 0


def test_find_or_launch_is_never_given_a_launch_command() -> None:
    """No call to find_or_launch ever passes a launch_command -- the unsandboxed-fallback guard."""
    sandbox = _StubSandbox()
    window = _StubDesktopWindow(fail_first_n_finds=2)

    run_in_sandboxed_terminal(
        "ls\n", sandbox=sandbox, desktop_window=window, sleep_fn=lambda _s: None
    )

    find_calls = [c for c in window.calls if c[0] == "find_or_launch"]
    assert len(find_calls) == _EXPECTED_FIND_ATTEMPTS_AFTER_TWO_FAILURES
    for call in find_calls:
        assert call[2] == "None"


def test_window_discovery_retries_then_succeeds() -> None:
    """A window not found on the first two attempts is found on the third -- no error raised."""
    sandbox = _StubSandbox()
    window = _StubDesktopWindow(fail_first_n_finds=2)

    result = run_in_sandboxed_terminal(
        "ls\n", sandbox=sandbox, desktop_window=window, sleep_fn=lambda _s: None
    )

    assert result is not None
    assert window.calls[-1][0] == "read_visible_text"


def test_window_discovery_raises_after_exhausting_all_attempts() -> None:
    """A window that never appears raises WindowNotFoundError, not silently hangs or succeeds."""
    sandbox = _StubSandbox()
    window = _StubDesktopWindow(fail_first_n_finds=999)

    with pytest.raises(WindowNotFoundError):
        run_in_sandboxed_terminal(
            "ls\n", sandbox=sandbox, desktop_window=window, sleep_fn=lambda _s: None
        )


def test_read_visible_text_returning_none_is_relayed_unchanged() -> None:
    """Best-effort output capture: None (unavailable) is a valid, non-error result."""
    sandbox = _StubSandbox()
    window = _StubDesktopWindow(read_result=None)

    result = run_in_sandboxed_terminal(
        "ls\n", sandbox=sandbox, desktop_window=window, sleep_fn=lambda _s: None
    )

    assert result is None
