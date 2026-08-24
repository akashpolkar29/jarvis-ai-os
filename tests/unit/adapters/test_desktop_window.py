"""Unit tests for jarvis.adapters.desktop_window.AtspiDesktopWindowAdapter.

What's faked and why: all five real AT-SPI2/subprocess entry points
(``find_app``, ``launch``, ``focus_fn``, ``type_text_fn``,
``read_text_fn``) are injected fakes -- no live accessibility bus or
real application is required, or reliably available, in CI or during
this unattended run (see the adapter module's own docstring for the
concrete reasons live verification was not attempted). Everything
these tests exercise is this adapter's own dispatch logic: handle-
token bookkeeping (a handle only resolves within the adapter instance
that issued it), the find-then-optionally-launch-then-retry flow, and
which port-level error each failure mode becomes.
"""

from __future__ import annotations

import pytest

from jarvis.adapters.desktop_window import AtspiDesktopWindowAdapter
from jarvis.domain.desktop import WindowHandle
from jarvis.ports.desktop_window import WindowActionFailedError, WindowNotFoundError

_REAL_APP = object()
_FOUND_ON_SECOND_POLL = 2


def test_find_or_launch_returns_a_handle_when_the_app_is_already_running() -> None:
    """A found app produces a handle carrying app_id, with no launch attempted."""
    launch_calls: list[tuple[str, ...]] = []
    adapter = AtspiDesktopWindowAdapter(
        find_app=lambda app_id: _REAL_APP if app_id == "code" else None,
        launch=launch_calls.append,
    )

    handle = adapter.find_or_launch("code")

    assert handle.app_id == "code"
    assert launch_calls == []


def test_find_or_launch_launches_and_retries_when_not_initially_found() -> None:
    """Not found + a launch_command given: the adapter launches, then retries discovery."""
    calls = {"find": 0}

    def find_app(app_id: str) -> object | None:  # noqa: ARG001
        calls["find"] += 1
        return _REAL_APP if calls["find"] >= _FOUND_ON_SECOND_POLL else None

    launch_calls: list[tuple[str, ...]] = []
    adapter = AtspiDesktopWindowAdapter(
        find_app=find_app,
        launch=launch_calls.append,
        sleep_fn=lambda _seconds: None,
    )

    handle = adapter.find_or_launch("code", launch_command=("code",))

    assert handle.app_id == "code"
    assert launch_calls == [("code",)]


def test_find_or_launch_raises_when_not_found_and_no_launch_command_given() -> None:
    """No launch_command: a not-found app raises immediately, no launch attempted."""
    launch_calls: list[tuple[str, ...]] = []
    adapter = AtspiDesktopWindowAdapter(find_app=lambda _app_id: None, launch=launch_calls.append)

    with pytest.raises(WindowNotFoundError):
        adapter.find_or_launch("nonexistent")

    assert launch_calls == []


def test_find_or_launch_raises_when_launch_never_produces_a_discoverable_window() -> None:
    """Launched but still never found after polling: WindowNotFoundError, not a hang."""
    launch_calls: list[tuple[str, ...]] = []
    adapter = AtspiDesktopWindowAdapter(
        find_app=lambda _app_id: None,
        launch=launch_calls.append,
        sleep_fn=lambda _seconds: None,
    )

    with pytest.raises(WindowNotFoundError):
        adapter.find_or_launch("nonexistent", launch_command=("nonexistent",))

    assert launch_calls == [("nonexistent",)]


def test_focus_calls_focus_fn_with_the_resolved_app() -> None:
    """focus() resolves the handle's token back to the real app object and delegates."""
    seen: list[object] = []

    def focus_fn(app: object) -> bool:
        seen.append(app)
        return True

    adapter = AtspiDesktopWindowAdapter(find_app=lambda _app_id: _REAL_APP, focus_fn=focus_fn)
    handle = adapter.find_or_launch("code")

    adapter.focus(handle)

    assert seen == [_REAL_APP]


def test_focus_raises_window_action_failed_when_focus_fn_returns_false() -> None:
    """A real focus attempt that fails (returns False) becomes WindowActionFailedError."""
    adapter = AtspiDesktopWindowAdapter(
        find_app=lambda _app_id: _REAL_APP, focus_fn=lambda _app: False
    )
    handle = adapter.find_or_launch("code")

    with pytest.raises(WindowActionFailedError):
        adapter.focus(handle)


def test_type_text_delegates_app_and_text_to_type_text_fn() -> None:
    """type_text() passes both the resolved app and the literal text through unchanged."""
    seen: list[tuple[object, str]] = []

    def type_text_fn(app: object, text: str) -> bool:
        seen.append((app, text))
        return True

    adapter = AtspiDesktopWindowAdapter(
        find_app=lambda _app_id: _REAL_APP, type_text_fn=type_text_fn
    )
    handle = adapter.find_or_launch("code")

    adapter.type_text(handle, "pytest\n")

    assert seen == [(_REAL_APP, "pytest\n")]


def test_type_text_raises_window_action_failed_when_no_editable_control_is_found() -> None:
    """type_text_fn returning False (no editable descendant found) becomes a real error."""
    adapter = AtspiDesktopWindowAdapter(
        find_app=lambda _app_id: _REAL_APP, type_text_fn=lambda _app, _text: False
    )
    handle = adapter.find_or_launch("code")

    with pytest.raises(WindowActionFailedError):
        adapter.type_text(handle, "hello")


def test_read_visible_text_returns_whatever_read_text_fn_returns() -> None:
    """read_visible_text() relays read_text_fn's result unchanged, including None."""
    adapter = AtspiDesktopWindowAdapter(
        find_app=lambda _app_id: _REAL_APP, read_text_fn=lambda _app: "some output"
    )
    handle = adapter.find_or_launch("code")

    assert adapter.read_visible_text(handle) == "some output"


def test_read_visible_text_returns_none_when_unavailable_rather_than_raising() -> None:
    """No Text interface on the target app is a real, expected outcome -- None, not an error."""
    adapter = AtspiDesktopWindowAdapter(
        find_app=lambda _app_id: _REAL_APP, read_text_fn=lambda _app: None
    )
    handle = adapter.find_or_launch("code")

    assert adapter.read_visible_text(handle) is None


def test_a_handle_from_a_different_adapter_instance_does_not_resolve() -> None:
    """A handle only means something to the adapter instance that issued it."""
    adapter = AtspiDesktopWindowAdapter(find_app=lambda _app_id: _REAL_APP)
    foreign_handle = WindowHandle(value="code:999999", app_id="code")

    with pytest.raises(WindowActionFailedError):
        adapter.focus(foreign_handle)
