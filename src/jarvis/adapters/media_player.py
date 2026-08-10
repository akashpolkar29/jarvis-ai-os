"""Adapters implementing jarvis.ports.media_player.MediaPlayerPort.

:class:`MprisMediaPlayerAdapter` talks to whatever media player is
currently running on the session bus via MPRIS
(https://specifications.freedesktop.org/mpris-spec/latest/), the
D-Bus interface every major Linux media player (Spotify, VLC, Firefox,
Chrome, and others) already implements natively. There is no new
protocol here -- this adapter is a thin translation from
``play()``/``pause()``/``next_track()``/``previous_track()`` calls to
the corresponding ``org.mpris.MediaPlayer2.Player`` D-Bus method calls.

Discovery, not configuration: MPRIS players register a D-Bus service
name of the form ``org.mpris.MediaPlayer2.<name>`` on the session bus.
This adapter asks the bus daemon itself (``org.freedesktop.DBus.ListNames``)
which such names currently exist and uses the first one found. If more
than one player is running, there is no priority or selection logic --
whichever ``ListNames`` returns first is the one controlled. Real
multi-player selection is future work, not built speculatively here.
If none is found, :class:`~jarvis.ports.media_player.NoMediaPlayerRunningError`
is raised before any command is sent. If a player is found but rejects
the actual command (e.g. a D-Bus error reply, including a security
policy like AppArmor denying the call),
:class:`~jarvis.ports.media_player.MediaPlayerCommandFailedError` is
raised instead. A ``DBusErrorResponse`` from the ``ListNames`` call
itself, as opposed to the actual command, is not specially converted
-- the bus daemon refusing to answer that is a much rarer, more
fundamentally broken scenario than one specific service rejecting one
command, and is not given its own typed handling here.

Testability seam: all the actual D-Bus wire mechanics (opening a
connection, building and sending a message, closing the connection)
live in one small function, :func:`_send_method_call_over_dbus`, which
is injectable via the constructor. Unit tests fake this single
function rather than a real bus connection -- faking jeepney's exact
reply-message wire format would mostly test the fake, not this
adapter's own discovery-then-dispatch logic (which the tests do cover
for real). :func:`_send_method_call_over_dbus` itself has no automated
test: it requires a live D-Bus session bus, which is exactly what
cannot be relied on in CI. Its correctness is proven by manual
verification against a real, running media player instead.

:func:`_unwrap_reply`, by contrast, is deliberately factored out as
its own pure, I/O-free function specifically so it CAN be unit-tested
directly, with a fake reply object, no bus required. This is the
function that actually detects a D-Bus error-type reply -- the exact
logic that was missing when an AppArmor-denied Pause call against a
real player was silently swallowed as success during manual
verification (jeepney's low-level ``send_and_get_reply``, unlike its
higher-level Proxy API, does not raise on an error reply by itself).
Keeping the bus I/O in ``_send_method_call_over_dbus`` as thin as
possible, and the actual error-detection logic in a separate,
directly-testable function, means the exact class of bug that slipped
through the first time now has real regression coverage instead of
being coverage only of a downstream consumer of an already-raised
exception.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from jeepney import DBusAddress, DBusErrorResponse, MessageType, new_method_call
from jeepney.io.blocking import open_dbus_connection

from jarvis.ports.media_player import MediaPlayerCommandFailedError, NoMediaPlayerRunningError

if TYPE_CHECKING:
    from collections.abc import Callable

    from jeepney import Message

    SendMethodCall = Callable[[DBusAddress, str], "tuple[object, ...]"]

_BUS_ADDRESS = DBusAddress(
    object_path="/org/freedesktop/DBus",
    bus_name="org.freedesktop.DBus",
    interface="org.freedesktop.DBus",
)
_MPRIS_PREFIX = "org.mpris.MediaPlayer2."
_PLAYER_OBJECT_PATH = "/org/mpris/MediaPlayer2"
_PLAYER_INTERFACE = "org.mpris.MediaPlayer2.Player"
_CALL_TIMEOUT_SECONDS = 5.0


def _unwrap_reply(reply: Message) -> tuple[object, ...]:
    """Return a reply's body, or raise DBusErrorResponse if it's an error-type reply.

    Pure and I/O-free -- unlike ``_send_method_call_over_dbus``, this
    IS unit-tested directly, with a fake reply object standing in for
    both an error-type and a normal-type message. This is the actual
    check that was missing before manual verification caught the
    AppArmor-denial bug: jeepney's low-level API returns an error
    reply's body as if it were a normal one, so this has to be
    detected explicitly rather than relied on to raise by itself.
    """
    if reply.header.message_type == MessageType.error:
        raise DBusErrorResponse(reply)
    return cast("tuple[object, ...]", reply.body)


def _send_method_call_over_dbus(address: DBusAddress, method: str) -> tuple[object, ...]:
    """Open a session-bus connection, send one method call, return the unwrapped reply body.

    The one real, untested-by-design piece of this module -- see the
    module docstring for why. A fresh connection is opened and closed
    per call, matching a CLI invocation's own short-lived-process
    shape: there is no persistent session to reuse. Deliberately thin:
    the only logic here is opening/sending/closing; error detection
    lives entirely in :func:`_unwrap_reply`.
    """
    with open_dbus_connection(bus="SESSION") as connection:
        message = new_method_call(address, method)
        reply = connection.send_and_get_reply(message, timeout=_CALL_TIMEOUT_SECONDS)
        return _unwrap_reply(reply)


class MprisMediaPlayerAdapter:
    """Controls whichever MPRIS media player is running on the session bus."""

    def __init__(self, send_method_call: SendMethodCall | None = None) -> None:
        """Store the function used to actually send a D-Bus method call.

        Args:
            send_method_call: Given a ``DBusAddress`` and a method
                name, sends the call and returns the reply body.
                Defaults to a real implementation talking to the
                session bus. Overridable for tests, exactly as
                ``AuthorizationOrchestrator``'s confirmation port is
                (WP-11) -- no I/O happens at construction time either
                way.
        """
        self._send_method_call: SendMethodCall = send_method_call or _send_method_call_over_dbus

    def play(self) -> None:
        """Resume playback on the first discovered MPRIS player."""
        self._invoke("Play")

    def pause(self) -> None:
        """Pause playback on the first discovered MPRIS player."""
        self._invoke("Pause")

    def next_track(self) -> None:
        """Skip to the next track on the first discovered MPRIS player."""
        self._invoke("Next")

    def previous_track(self) -> None:
        """Go back to the previous track on the first discovered MPRIS player."""
        self._invoke("Previous")

    def _invoke(self, method: str) -> None:
        """Discover the running player and send it ``method`` with no arguments.

        Raises:
            NoMediaPlayerRunningError: If discovery finds no player.
            MediaPlayerCommandFailedError: If a player was found but
                the command itself was rejected (e.g. a D-Bus-level
                error reply, including a security policy like AppArmor
                denying the call).
        """
        service_name = self._discover_player()
        player_address = DBusAddress(
            object_path=_PLAYER_OBJECT_PATH,
            bus_name=service_name,
            interface=_PLAYER_INTERFACE,
        )
        try:
            self._send_method_call(player_address, method)
        except DBusErrorResponse as exc:
            msg = f"{method} was rejected by the D-Bus service: {exc}"
            raise MediaPlayerCommandFailedError(msg) from exc

    def _discover_player(self) -> str:
        """Return the first ``org.mpris.MediaPlayer2.*`` name currently on the bus.

        Raises:
            NoMediaPlayerRunningError: If no such name exists.
        """
        body = self._send_method_call(_BUS_ADDRESS, "ListNames")
        names = cast("list[str]", body[0])
        mpris_names = [name for name in names if name.startswith(_MPRIS_PREFIX)]
        if not mpris_names:
            msg = "No MPRIS media player is currently running on the session bus."
            raise NoMediaPlayerRunningError(msg)
        return mpris_names[0]
