"""Unit tests for jarvis.application.desktop.terminal.run_in_sandboxed_terminal.

What's mocked and why: stub SandboxPort/DesktopWindowPort/
SyntheticInputPort/SecretPort/TtsPort (with call tracking) stand in for
their real adapters -- these tests must be hermetic and never actually
launch a real, visible terminal window, open a real portal session, or
speak real audio. sleep_fn is always a no-op injection so retry-loop
tests run instantly rather than waiting real seconds.

This is the safety-critical logic ADR-0047 is built around --
extra weight is given here to the hard-abort precondition (zero
keystrokes if the indicator cannot be shown) and the per-character
fail-closed focus verification (abort every remaining character the
instant one check fails), not just the happy path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from jarvis.application.desktop.terminal import _char_to_keysym, run_in_sandboxed_terminal
from jarvis.domain.audio import AudioStream
from jarvis.domain.desktop import SyntheticInputSession, WindowHandle
from jarvis.ports.desktop_window import WindowNotFoundError
from jarvis.ports.secret import SecretNotFoundError
from jarvis.ports.synthetic_input import SyntheticInputUnavailableError

if TYPE_CHECKING:
    from jarvis.domain.process import CommandResult

_TERMINAL_APP_ID = "gnome-terminal"
_FAKE_PID = 12345
_EXPECTED_FIND_ATTEMPTS_AFTER_TWO_FAILURES = 3
_FAKE_PROFILE_UUID = "fixed-profile-uuid"
_FAKE_AUDIO = AudioStream(samples=b"\x00\x00", sample_rate=22050)
_FAKE_SESSION = SyntheticInputSession(session_handle="/session/1", new_restore_token=None)
_TWO_CHARS_TYPED_AS_KEYSYM_PAIRS = 4
_ONE_CHAR_TYPED_AS_KEYSYM_PAIRS = 2
_RETURN_KEYSYM = 0xFF0D
_TAB_KEYSYM = 0xFF09


class _StubSandbox:
    """A SandboxPort test double that records launch() calls, in order."""

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
        allow_display: bool = False,  # noqa: ARG002
    ) -> int:
        """Record a launch() call and return a fake pid."""
        self.calls.append(("launch", *command))
        return _FAKE_PID


class _StubDesktopWindow:
    """A DesktopWindowPort test double, with configurable focus/visibility results.

    find_or_launch fails a configurable number of times before
    succeeding, to exercise _find_the_sandboxed_terminal_window's
    retry loop for real. is_focused_results, if given, is popped from
    left to right on each is_focused() call (one entry per call);
    otherwise a single fixed value is always returned.
    """

    def __init__(
        self,
        *,
        fail_first_n_finds: int = 0,
        read_result: str | None = "$ ",
        visible_and_showing: bool = True,
        is_focused_results: list[bool] | None = None,
    ) -> None:
        """Configure this double's behavior for the scenario under test."""
        self.calls: list[tuple[str, ...]] = []
        self._remaining_failures = fail_first_n_finds
        self._read_result = read_result
        self._visible_and_showing = visible_and_showing
        self._is_focused_results = (
            list(is_focused_results) if is_focused_results is not None else None
        )
        self._fixed_focused = True

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
        """Record a type_text() call -- unused by ADR-0047's flow, kept only to satisfy the port."""
        self.calls.append(("type_text", handle.app_id, text))

    def read_visible_text(self, handle: WindowHandle) -> str | None:
        """Record a read_visible_text() call and return the configured result."""
        self.calls.append(("read_visible_text", handle.app_id))
        return self._read_result

    def is_focused(self, handle: WindowHandle) -> bool:
        """Record an is_focused() call and return the next configured result."""
        self.calls.append(("is_focused", handle.app_id))
        if self._is_focused_results is not None:
            return self._is_focused_results.pop(0)
        return self._fixed_focused

    def is_visible_and_showing(self, handle: WindowHandle) -> bool:
        """Record an is_visible_and_showing() call and return the configured result."""
        self.calls.append(("is_visible_and_showing", handle.app_id))
        return self._visible_and_showing


class _StubSyntheticInput:
    """A SyntheticInputPort test double that records start_session()/send_keysym() calls."""

    def __init__(self, *, session: SyntheticInputSession = _FAKE_SESSION) -> None:
        """Start with an empty call log and a fixed session to return from start_session()."""
        self.calls: list[tuple[object, ...]] = []
        self._session = session

    def start_session(self, restore_token: str | None) -> SyntheticInputSession:
        """Record a start_session() call and return the configured session."""
        self.calls.append(("start_session", restore_token))
        return self._session

    def send_keysym(self, session: SyntheticInputSession, keysym: int, *, press: bool) -> None:
        """Record a send_keysym() call."""
        self.calls.append(("send_keysym", session.session_handle, keysym, press))


class _StubSecret:
    """A SecretPort test double backed by a plain dict."""

    def __init__(self, *, initial: dict[str, str] | None = None) -> None:
        """Start with an optional pre-populated store and an empty call log."""
        self._store: dict[str, str] = dict(initial or {})
        self.set_calls: list[tuple[str, str]] = []

    def get_secret(self, reference: str) -> str:
        """Return the stored value, or raise SecretNotFoundError."""
        try:
            return self._store[reference]
        except KeyError:
            msg = f"No secret for {reference!r}."
            raise SecretNotFoundError(msg) from None

    def set_secret(self, reference: str, value: str) -> None:
        """Record a set_secret() call and store the value."""
        self.set_calls.append((reference, value))
        self._store[reference] = value


class _StubTts:
    """A TtsPort test double that records speak() calls and returns fixed audio, or raises."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        """Configure whether speak() succeeds (returning fixed audio) or raises."""
        self.calls: list[str] = []
        self._raises = raises

    async def speak(self, text: str) -> AudioStream:
        """Record a speak() call; raise if configured to, else return fixed audio."""
        self.calls.append(text)
        if self._raises is not None:
            raise self._raises
        return _FAKE_AUDIO


def _real_kwargs(**overrides: Any) -> dict[str, Any]:
    """Build a full, valid kwargs dict for run_in_sandboxed_terminal, with overrides applied."""
    play_calls: list[AudioStream] = []
    defaults: dict[str, Any] = {
        "sandbox": _StubSandbox(),
        "desktop_window": _StubDesktopWindow(),
        "synthetic_input": _StubSyntheticInput(),
        "secret": _StubSecret(),
        "tts": _StubTts(),
        "play_fn": play_calls.append,
        "ensure_profile": lambda: _FAKE_PROFILE_UUID,
        "sleep_fn": lambda _s: None,
    }
    defaults.update(overrides)
    return defaults


async def test_happy_path_runs_the_full_flow_in_order_and_returns_output() -> None:
    """launch(with profile), find, focus, visibility check, speak+play, session, type, read."""
    sandbox = _StubSandbox()
    window = _StubDesktopWindow(read_result="$ echo hi\nhi")
    synthetic_input = _StubSyntheticInput()
    tts = _StubTts()
    play_calls: list[AudioStream] = []

    result = await run_in_sandboxed_terminal(
        "hi\n",
        **_real_kwargs(
            sandbox=sandbox,
            desktop_window=window,
            synthetic_input=synthetic_input,
            tts=tts,
            play_fn=play_calls.append,
        ),
    )

    assert sandbox.calls == [("launch", "gnome-terminal", f"--profile={_FAKE_PROFILE_UUID}")]
    assert tts.calls == ["Typing into the sandboxed terminal now."]
    assert play_calls == [_FAKE_AUDIO]
    assert ("start_session", None) in synthetic_input.calls
    assert result == "$ echo hi\nhi"

    # Every character in "hi\n" produced a press/release keysym pair, in order.
    keysym_calls = [c for c in synthetic_input.calls if c[0] == "send_keysym"]
    assert keysym_calls == [
        ("send_keysym", "/session/1", _char_to_keysym("h"), True),
        ("send_keysym", "/session/1", _char_to_keysym("h"), False),
        ("send_keysym", "/session/1", _char_to_keysym("i"), True),
        ("send_keysym", "/session/1", _char_to_keysym("i"), False),
        ("send_keysym", "/session/1", _char_to_keysym("\n"), True),
        ("send_keysym", "/session/1", _char_to_keysym("\n"), False),
    ]


async def test_visibility_precondition_failing_aborts_before_any_speak_or_session() -> None:
    """Hard-abort precondition: not visible/showing -- zero keystrokes, zero speak, zero session."""
    window = _StubDesktopWindow(visible_and_showing=False)
    synthetic_input = _StubSyntheticInput()
    tts = _StubTts()

    with pytest.raises(SyntheticInputUnavailableError, match="not visible"):
        await run_in_sandboxed_terminal(
            "ls\n",
            **_real_kwargs(desktop_window=window, synthetic_input=synthetic_input, tts=tts),
        )

    assert tts.calls == []
    assert synthetic_input.calls == []


async def test_speak_failure_aborts_before_any_session_or_keystroke() -> None:
    """Hard-abort precondition: tts.speak() raising propagates -- not caught, zero keystrokes."""
    window = _StubDesktopWindow(visible_and_showing=True)
    synthetic_input = _StubSyntheticInput()
    tts = _StubTts(raises=RuntimeError("no audio device"))

    with pytest.raises(RuntimeError, match="no audio device"):
        await run_in_sandboxed_terminal(
            "ls\n",
            **_real_kwargs(desktop_window=window, synthetic_input=synthetic_input, tts=tts),
        )

    assert synthetic_input.calls == []


async def test_focus_lost_mid_command_aborts_remaining_characters() -> None:
    """Fail-closed: is_focused() False on the second character aborts everything after it."""
    # "abc": is_focused checked before each char -- True, True, then False before 'c'.
    window = _StubDesktopWindow(is_focused_results=[True, True, False])
    synthetic_input = _StubSyntheticInput()

    with pytest.raises(SyntheticInputUnavailableError, match="Focus was lost mid-command"):
        await run_in_sandboxed_terminal(
            "abc",
            **_real_kwargs(desktop_window=window, synthetic_input=synthetic_input),
        )

    keysym_calls = [c for c in synthetic_input.calls if c[0] == "send_keysym"]
    # Only 'a' and 'b' were typed (2 chars * press+release) -- 'c' never sent.
    assert len(keysym_calls) == _TWO_CHARS_TYPED_AS_KEYSYM_PAIRS
    assert all(call[2] in (_char_to_keysym("a"), _char_to_keysym("b")) for call in keysym_calls)


async def test_focus_lost_after_last_character_still_raises() -> None:
    """The final post-loop focus check matters even when every character was sent."""
    window = _StubDesktopWindow(is_focused_results=[True, False])
    synthetic_input = _StubSyntheticInput()

    with pytest.raises(SyntheticInputUnavailableError, match="Focus was lost after the last"):
        await run_in_sandboxed_terminal(
            "a",
            **_real_kwargs(desktop_window=window, synthetic_input=synthetic_input),
        )

    keysym_calls = [c for c in synthetic_input.calls if c[0] == "send_keysym"]
    # 'a' was sent (press+release) before the post-loop focus check failed.
    assert len(keysym_calls) == _ONE_CHAR_TYPED_AS_KEYSYM_PAIRS


async def test_focus_held_throughout_sends_every_character_and_returns() -> None:
    """The non-flaky happy path: is_focused() True on every check, all characters sent."""
    window = _StubDesktopWindow(is_focused_results=[True, True, True])

    result = await run_in_sandboxed_terminal(
        "ab", **_real_kwargs(desktop_window=window, sleep_fn=lambda _s: None)
    )

    assert result is not None


async def test_no_stored_restore_token_starts_a_session_with_none() -> None:
    """SecretNotFoundError from get_secret() means start_session(None) -- first-ever use."""
    synthetic_input = _StubSyntheticInput()
    secret = _StubSecret()

    await run_in_sandboxed_terminal(
        "x", **_real_kwargs(synthetic_input=synthetic_input, secret=secret)
    )

    assert ("start_session", None) in synthetic_input.calls


async def test_a_stored_restore_token_is_passed_to_start_session() -> None:
    """A previously-persisted token is replayed, not discarded."""
    synthetic_input = _StubSyntheticInput()
    secret = _StubSecret(initial={"desktop.synthetic_input.restore_token": "stored-token"})

    await run_in_sandboxed_terminal(
        "x", **_real_kwargs(synthetic_input=synthetic_input, secret=secret)
    )

    assert ("start_session", "stored-token") in synthetic_input.calls


async def test_a_new_restore_token_is_persisted_via_set_secret() -> None:
    """A session that returns a new_restore_token has it written back through SecretPort."""
    session_with_token = SyntheticInputSession(
        session_handle="/session/1", new_restore_token="new-token"
    )
    synthetic_input = _StubSyntheticInput(session=session_with_token)
    secret = _StubSecret()

    await run_in_sandboxed_terminal(
        "x", **_real_kwargs(synthetic_input=synthetic_input, secret=secret)
    )

    assert secret.set_calls == [("desktop.synthetic_input.restore_token", "new-token")]


async def test_no_new_restore_token_means_set_secret_is_never_called() -> None:
    """A replayed session with no rotated token does not trigger a spurious write."""
    synthetic_input = _StubSyntheticInput(session=_FAKE_SESSION)  # new_restore_token=None
    secret = _StubSecret()

    await run_in_sandboxed_terminal(
        "x", **_real_kwargs(synthetic_input=synthetic_input, secret=secret)
    )

    assert secret.set_calls == []


async def test_launch_always_happens_before_send_keysym() -> None:
    """sandbox.launch() is called before any real keystroke -- the real ADR-0046/0047 ordering."""
    sandbox = _StubSandbox()
    synthetic_input = _StubSyntheticInput()

    await run_in_sandboxed_terminal(
        "ls\n", **_real_kwargs(sandbox=sandbox, synthetic_input=synthetic_input)
    )

    assert sandbox.calls != []
    assert any(c[0] == "send_keysym" for c in synthetic_input.calls)


async def test_find_or_launch_is_never_given_a_launch_command() -> None:
    """No call to find_or_launch ever passes a launch_command -- the unsandboxed-fallback guard."""
    window = _StubDesktopWindow(fail_first_n_finds=2)

    await run_in_sandboxed_terminal("ls\n", **_real_kwargs(desktop_window=window))

    find_calls = [c for c in window.calls if c[0] == "find_or_launch"]
    assert len(find_calls) == _EXPECTED_FIND_ATTEMPTS_AFTER_TWO_FAILURES
    for call in find_calls:
        assert call[2] == "None"


async def test_window_discovery_retries_then_succeeds() -> None:
    """A window not found on the first two attempts is found on the third -- no error raised."""
    window = _StubDesktopWindow(fail_first_n_finds=2)

    result = await run_in_sandboxed_terminal("ls\n", **_real_kwargs(desktop_window=window))

    assert result is not None


async def test_window_discovery_raises_after_exhausting_all_attempts() -> None:
    """A window that never appears raises WindowNotFoundError, not silently hangs or succeeds."""
    window = _StubDesktopWindow(fail_first_n_finds=999)

    with pytest.raises(WindowNotFoundError):
        await run_in_sandboxed_terminal("ls\n", **_real_kwargs(desktop_window=window))


async def test_read_visible_text_returning_none_is_relayed_unchanged() -> None:
    """Best-effort output capture: None (unavailable) is a valid, non-error result."""
    window = _StubDesktopWindow(read_result=None)

    result = await run_in_sandboxed_terminal("ls\n", **_real_kwargs(desktop_window=window))

    assert result is None


def test_char_to_keysym_maps_newline_to_the_return_keysym() -> None:
    """Terminals interpret Return specially -- not the raw codepoint of '\\n'."""
    assert _char_to_keysym("\n") == _RETURN_KEYSYM


def test_char_to_keysym_maps_tab_to_the_tab_keysym() -> None:
    """Terminals interpret Tab specially -- not the raw codepoint of '\\t'."""
    assert _char_to_keysym("\t") == _TAB_KEYSYM


def test_char_to_keysym_maps_printable_ascii_to_its_own_codepoint() -> None:
    """The real X11 fact ADR-0047 relies on: Latin-1 keysyms equal their codepoint."""
    assert _char_to_keysym("a") == ord("a")
    assert _char_to_keysym("Z") == ord("Z")
    assert _char_to_keysym(" ") == ord(" ")


def test_char_to_keysym_maps_non_latin1_unicode_via_the_unicode_offset() -> None:
    """A character outside Latin-1 uses the X11 Unicode keysym convention."""
    assert _char_to_keysym("€") == 0x01000000 + ord("€")
