"""Unit tests for jarvis.adapters.media_player.MprisMediaPlayerAdapter.

What's mocked and why: only the actual D-Bus wire I/O
(``send_method_call``) is faked -- no real session bus is required, or
reliably available, in CI. Everything these tests exercise is this
adapter's own discovery-then-dispatch logic: which service name it
picks from a ListNames reply, what method name and destination it
sends for each of the four commands, and that it raises before sending
anything when no MPRIS player is present. The low-level jeepney
plumbing this fake stands in for (`_send_method_call_over_dbus`) has
no automated test -- see adapters/media_player.py's module docstring
for why -- and is proven correct by manual verification instead.

The ``_unwrap_reply`` tests below are the actual regression coverage
for the AppArmor-denial bug found during manual verification: jeepney's
low-level ``send_and_get_reply`` does not raise on a D-Bus error-type
reply by itself, so ``_unwrap_reply`` has to detect this by checking
``reply.header.message_type``. Testing this directly, with a fake
reply object carrying ``MessageType.error``, exercises the exact
detection logic that was missing -- not just a downstream consumer of
an already-raised exception (which is what ``test_a_rejected_command_
raises_media_player_command_failed_error`` below tests instead, a
different and still-valid concern: that ``_invoke`` correctly converts
whatever raises ``DBusErrorResponse`` into ``MediaPlayerCommandFailedError``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from jeepney import DBusErrorResponse, MessageType

from jarvis.adapters.media_player import MprisMediaPlayerAdapter, _unwrap_reply
from jarvis.ports.media_player import MediaPlayerCommandFailedError, NoMediaPlayerRunningError

if TYPE_CHECKING:
    from jeepney import DBusAddress

_ONE_MPRIS_PLAYER = ["org.mpris.MediaPlayer2.vlc", "org.freedesktop.Notifications"]
_TWO_MPRIS_PLAYERS = ["org.mpris.MediaPlayer2.vlc", "org.mpris.MediaPlayer2.spotify"]
_NO_MPRIS_PLAYERS = ["org.freedesktop.Notifications"]


def _fake_send(
    names: list[str],
) -> tuple[list[tuple[str, str]], object]:
    """Build a fake send_method_call that answers ListNames with `names` and logs every call."""
    calls: list[tuple[str, str]] = []

    def send(address: DBusAddress, method: str) -> tuple[object, ...]:
        calls.append((address.bus_name, method))
        if method == "ListNames":
            return (names,)
        return ()

    return calls, send


def test_pause_sends_pause_to_the_first_discovered_mpris_player() -> None:
    """pause() discovers the running player, then sends it Pause on the Player interface."""
    calls, send = _fake_send(_ONE_MPRIS_PLAYER)
    adapter = MprisMediaPlayerAdapter(send_method_call=send)  # type: ignore[arg-type]

    adapter.pause()

    assert calls == [
        ("org.freedesktop.DBus", "ListNames"),
        ("org.mpris.MediaPlayer2.vlc", "Pause"),
    ]


def test_play_sends_play() -> None:
    """play() sends the Play method."""
    calls, send = _fake_send(_ONE_MPRIS_PLAYER)
    adapter = MprisMediaPlayerAdapter(send_method_call=send)  # type: ignore[arg-type]

    adapter.play()

    assert calls[-1] == ("org.mpris.MediaPlayer2.vlc", "Play")


def test_next_track_sends_next() -> None:
    """next_track() sends the Next method."""
    calls, send = _fake_send(_ONE_MPRIS_PLAYER)
    adapter = MprisMediaPlayerAdapter(send_method_call=send)  # type: ignore[arg-type]

    adapter.next_track()

    assert calls[-1] == ("org.mpris.MediaPlayer2.vlc", "Next")


def test_previous_track_sends_previous() -> None:
    """previous_track() sends the Previous method."""
    calls, send = _fake_send(_ONE_MPRIS_PLAYER)
    adapter = MprisMediaPlayerAdapter(send_method_call=send)  # type: ignore[arg-type]

    adapter.previous_track()

    assert calls[-1] == ("org.mpris.MediaPlayer2.vlc", "Previous")


def test_uses_the_first_mpris_name_when_multiple_players_are_running() -> None:
    """With two players registered, whichever ListNames returns first is the one controlled.

    Documents the adapter's stated limitation: no priority/selection
    logic, this is deliberate (see the module docstring).
    """
    calls, send = _fake_send(_TWO_MPRIS_PLAYERS)
    adapter = MprisMediaPlayerAdapter(send_method_call=send)  # type: ignore[arg-type]

    adapter.play()

    assert calls[-1] == ("org.mpris.MediaPlayer2.vlc", "Play")


def test_raises_when_no_mpris_player_is_running() -> None:
    """With no MPRIS name on the bus, NoMediaPlayerRunningError is raised."""
    _calls, send = _fake_send(_NO_MPRIS_PLAYERS)
    adapter = MprisMediaPlayerAdapter(send_method_call=send)  # type: ignore[arg-type]

    with pytest.raises(NoMediaPlayerRunningError):
        adapter.pause()


def test_no_command_is_sent_when_no_player_is_running() -> None:
    """When discovery finds nothing, only ListNames was ever called -- no Pause/Play/etc."""
    calls, send = _fake_send(_NO_MPRIS_PLAYERS)
    adapter = MprisMediaPlayerAdapter(send_method_call=send)  # type: ignore[arg-type]

    with pytest.raises(NoMediaPlayerRunningError):
        adapter.pause()

    assert calls == [("org.freedesktop.DBus", "ListNames")]


class _FakeReplyHeader:
    """A minimal stand-in for jeepney's Message.header.

    Carries both attributes anything downstream reads: message_type
    (what _unwrap_reply itself checks) and fields (what
    DBusErrorResponse's own constructor reads, only reached once
    _unwrap_reply has already decided this is an error reply).
    """

    def __init__(self, message_type: MessageType) -> None:
        """Store the message type; fields stays empty (nothing here reads specific fields)."""
        self.message_type = message_type
        self.fields: dict[object, object] = {}


class _FakeReplyMessage:
    """A minimal stand-in for jeepney's Message -- enough for _unwrap_reply/DBusErrorResponse."""

    def __init__(self, message_type: MessageType, body: tuple[object, ...] = ()) -> None:
        """Build a fake reply with the given message type and body."""
        self.header = _FakeReplyHeader(message_type)
        self.body = body


def test_unwrap_reply_raises_dbus_error_response_for_an_error_type_reply() -> None:
    """An error-type reply raises DBusErrorResponse -- the actual regression test for the bug.

    This is the exact check that was missing: jeepney's
    send_and_get_reply does not raise on an error-type reply on its
    own, it just returns it. Before _unwrap_reply existed, an
    AppArmor-denied Pause call against a real, running player was
    silently treated as a success -- no mocked test caught it, because
    every existing fake only ever returned what it was told to, and
    nothing was telling it to simulate an actual error-type reply.
    """
    error_reply = _FakeReplyMessage(MessageType.error, body=("Permission denied",))

    with pytest.raises(DBusErrorResponse):
        _unwrap_reply(error_reply)


def test_unwrap_reply_returns_the_body_for_a_normal_reply() -> None:
    """A normal (method_return) reply's body is returned as-is, not treated as an error."""
    normal_reply = _FakeReplyMessage(MessageType.method_return, body=("ok",))

    assert _unwrap_reply(normal_reply) == ("ok",)


def test_a_rejected_command_raises_media_player_command_failed_error() -> None:
    """A player found but rejecting the command raises MediaPlayerCommandFailedError.

    A different concern from the _unwrap_reply tests above: this
    tests that _invoke correctly converts a DBusErrorResponse --
    however it was raised -- into the port-level
    MediaPlayerCommandFailedError. Simulated here via a fake
    send_method_call that raises DBusErrorResponse directly for the
    actual command, exactly what _send_method_call_over_dbus now does
    (via _unwrap_reply) for a real D-Bus error reply.
    """

    def send(address: DBusAddress, method: str) -> tuple[object, ...]:  # noqa: ARG001
        if method == "ListNames":
            return (_ONE_MPRIS_PLAYER,)
        raise DBusErrorResponse(_FakeReplyMessage(MessageType.error, body=("denied",)))

    adapter = MprisMediaPlayerAdapter(send_method_call=send)

    with pytest.raises(MediaPlayerCommandFailedError):
        adapter.pause()
