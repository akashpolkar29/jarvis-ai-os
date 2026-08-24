"""Adapters implementing jarvis.ports.synthetic_input.SyntheticInputPort.

:class:`PortalSyntheticInputAdapter` talks to the real
``org.freedesktop.portal.RemoteDesktop`` portal (version 2, confirmed
live via ``gdbus introspect`` during ADR-0047's own design pass -- see
that ADR's Context section) via ``jeepney``, the same D-Bus library
``adapters/media_player.py``/``adapters/secret.py`` already use. No new
protocol dependency.

**Real, load-bearing limitation of this pass, stated plainly rather
than rounded up**: unlike every other real-D-Bus adapter in this repo
(MPRIS, Secret Service), this module's low-level wire mechanics have
**not been exercised against a real bus at all this pass -- not even
manually**. Every other adapter's "untested-by-design" function is at
least proven correct by one real, manual round trip on this machine
(WP-32's Secret Service verification, this same work package's own
``adapters/secret.py`` write-path verification). That was correctly
*not* done here: a real ``CreateSession``/``SelectDevices``/``Start``
call pops a real, interactive OS permission dialog on the user's live
screen, and WP-56's own scope explicitly excludes triggering that
unattended (ADR-0047's own reasoning: this needs the user physically
present). The exact wire shapes below (option/result dict keys, device
type bitmask values, the ``Request.Response`` signal mechanics) come
from the portal's own published specification
(https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html),
cross-checked against this machine's real, live ``gdbus introspect``
output for the method signatures (matching ADR-0047's own Context
section). The variant-decoding shape used to read ``Response`` signal
results (each ``a{sv}`` value arrives as a real ``(signature, value)``
tuple) *was* verified live this pass -- by round-tripping a
synthetic message through jeepney's own real serializer/parser
directly, which needs no bus at all -- so that specific piece is
real-verified, not merely read from documentation. The genuine, open
gap this leaves: the live-verification session (physically present,
per ADR-0047) is the first time ``_open_portal_session`` will actually
run end-to-end, and is exactly the place a wire-format mistake this
pass could not catch would surface.

Testability seam, matching every other real-D-Bus adapter in this
repo: the actual wire mechanics live in two small, injectable,
untested-by-design functions (:func:`_open_portal_session`,
:func:`_notify_keysym`). Unit tests fake both and exercise only this
adapter's own dispatch logic: the "one automatic fallback attempt on a
failed token replay, never retried beyond that" control flow ADR-0047's
``restore_token`` lifecycle specifies. :func:`_unwrap_variant` and
:func:`_decode_response`, by contrast, are pure and directly
unit-tested with no bus required, the same role
``_unwrap_reply``/``_find_secret_value`` play in the adapters they
belong to.
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, cast

from jeepney import DBusAddress, MatchRule, new_method_call
from jeepney.bus_messages import DBus as MessageBusAddress
from jeepney.io.blocking import open_dbus_connection

from jarvis.domain.desktop import SyntheticInputSession
from jarvis.ports.synthetic_input import SyntheticInputUnavailableError

if TYPE_CHECKING:
    from collections.abc import Callable

    from jeepney.io.blocking import DBusConnection

    # (new session_handle, new_restore_token or None)
    OpenSessionResult = tuple[str, "str | None"]
    OpenPortalSessionFn = Callable[["str | None"], OpenSessionResult]
    NotifyKeysymFn = Callable[[str, int, bool], None]
    Variant = tuple[str, object]
    Vardict = dict[str, Variant]

_PORTAL = DBusAddress(
    object_path="/org/freedesktop/portal/desktop",
    bus_name="org.freedesktop.portal.Desktop",
    interface="org.freedesktop.portal.RemoteDesktop",
)
_CALL_TIMEOUT_SECONDS = 5.0
_RESPONSE_WAIT_TIMEOUT_SECONDS = 120.0
"""Generous on purpose: this is the window a real human has to answer the
real, interactive permission dialog -- not a normal D-Bus call latency."""

_KEYBOARD_DEVICE_TYPE = 1
"""Per the portal's own documented bitmask (KEYBOARD=1, POINTER=2,
TOUCHSCREEN=4) -- only KEYBOARD is requested, matching ADR-0047's own
scope (Terminal typing only, no pointer/touch)."""

_PERSIST_UNTIL_REVOKED = 2
_KEY_STATE_RELEASED = 0
_KEY_STATE_PRESSED = 1
_RESPONSE_SUCCESS = 0


_handle_token_counter = itertools.count()
"""Backs _new_handle_token(). A plain in-process counter, not uuid4/time --
this project bans direct non-deterministic sources in src/ (ClockPort/
IdPort injection instead). No port injection is warranted here: these
tokens only need to be distinct within one adapter process's own
lifetime (see _new_handle_token's own docstring), the same "every
invocation is already a fresh, separate process" scope WindowHandle's
own docstring already establishes for a structurally identical need."""


def _new_handle_token() -> str:
    """A caller-chosen token the portal requires on every request method.

    Not used to predict the Request object's path (a real, documented
    source of subtle bugs if the sender-name-escaping rules are gotten
    wrong) -- this adapter always reads the real path back from the
    method call's own synchronous return value instead. Only present
    because the portal API requires *some* value here, and only needs
    to be distinct within this process's own lifetime.
    """
    return f"jarvis_{next(_handle_token_counter)}"


def _unwrap_variant(value: Variant) -> object:
    """Return a decoded ``a{sv}`` dict value's real payload, discarding its signature char.

    Pure and I/O-free -- directly unit-tested. jeepney decodes each
    ``a{sv}`` entry as a ``(signature, value)`` tuple (verified live
    this pass by round-tripping a synthetic message through jeepney's
    own real serializer/parser -- see the module docstring), not just
    the bare value a caller usually wants.
    """
    _signature, real_value = value
    return real_value


def _decode_response(body: tuple[object, ...]) -> tuple[int, Vardict]:
    """Return a Request.Response signal's ``(response_code, results)`` body, typed.

    Pure and I/O-free -- directly unit-tested with a fake signal body,
    no bus required.
    """
    response_code, results = body
    return cast("int", response_code), cast("Vardict", results)


def _await_request_response(connection: DBusConnection, request_path: str) -> tuple[int, Vardict]:
    """Block until ``request_path``'s Request.Response signal arrives, then return it, decoded.

    Registers a real bus-level match (``AddMatch``) before waiting,
    rather than relying on the Response signal being unicast to this
    connection without one -- correct either way, and the only
    defensible choice given this exact call was never exercised live
    this pass (see the module docstring).
    """
    rule = MatchRule(
        type="signal",
        interface="org.freedesktop.portal.Request",
        member="Response",
        path=request_path,
    )
    add_match_msg = MessageBusAddress().AddMatch(rule)
    connection.send_and_get_reply(add_match_msg, timeout=_CALL_TIMEOUT_SECONDS)

    with connection.filter(rule) as queue:
        signal = connection.recv_until_filtered(queue, timeout=_RESPONSE_WAIT_TIMEOUT_SECONDS)
    return _decode_response(signal.body)


def _create_session(connection: DBusConnection) -> str:
    """Real CreateSession call, blocked on its Request.Response signal. Returns the session_handle.

    Raises:
        SyntheticInputUnavailableError: If the request did not succeed.
    """
    options = {
        "handle_token": ("s", _new_handle_token()),
        "session_handle_token": ("s", _new_handle_token()),
    }
    msg = new_method_call(_PORTAL, "CreateSession", "a{sv}", (options,))
    reply = connection.send_and_get_reply(msg, timeout=_CALL_TIMEOUT_SECONDS)
    (request_path,) = reply.body

    response_code, results = _await_request_response(connection, cast("str", request_path))
    if response_code != _RESPONSE_SUCCESS:
        msg_text = f"RemoteDesktop CreateSession did not succeed (response code {response_code})."
        raise SyntheticInputUnavailableError(msg_text)
    return cast("str", _unwrap_variant(results["session_handle"]))


def _select_devices(
    connection: DBusConnection, session_handle: str, restore_token: str | None
) -> None:
    """Real SelectDevices call for KEYBOARD only, blocked on its Request.Response signal.

    Raises:
        SyntheticInputUnavailableError: If the request did not
            succeed -- including a rejected/invalid ``restore_token``,
            which this function does not distinguish from any other
            failure (the portal's own response code does not reliably
            do so either -- see :meth:`PortalSyntheticInputAdapter.start_session`
            for the one-fallback-attempt handling this ambiguity
            drives).
    """
    options: Vardict = {
        "handle_token": ("s", _new_handle_token()),
        "types": ("u", _KEYBOARD_DEVICE_TYPE),
        "persist_mode": ("u", _PERSIST_UNTIL_REVOKED),
    }
    if restore_token is not None:
        options["restore_token"] = ("s", restore_token)
    msg = new_method_call(_PORTAL, "SelectDevices", "oa{sv}", (session_handle, options))
    reply = connection.send_and_get_reply(msg, timeout=_CALL_TIMEOUT_SECONDS)
    (request_path,) = reply.body

    response_code, _results = _await_request_response(connection, cast("str", request_path))
    if response_code != _RESPONSE_SUCCESS:
        msg_text = f"RemoteDesktop SelectDevices did not succeed (response code {response_code})."
        raise SyntheticInputUnavailableError(msg_text)


def _start(connection: DBusConnection, session_handle: str) -> str | None:
    """Real Start call, blocked on its Request.Response signal. Returns a new restore_token, if any.

    This is the call that pops the real, interactive OS permission
    dialog on first use (or on an invalid/expired restore_token) --
    the generous ``_RESPONSE_WAIT_TIMEOUT_SECONDS`` above is sized for
    this, not for a normal D-Bus round trip.

    Raises:
        SyntheticInputUnavailableError: If the request did not succeed
            (including the human denying the dialog).
    """
    options = {"handle_token": ("s", _new_handle_token())}
    msg = new_method_call(_PORTAL, "Start", "osa{sv}", (session_handle, "", options))
    reply = connection.send_and_get_reply(msg, timeout=_CALL_TIMEOUT_SECONDS)
    (request_path,) = reply.body

    response_code, results = _await_request_response(connection, cast("str", request_path))
    if response_code != _RESPONSE_SUCCESS:
        msg_text = f"RemoteDesktop Start did not succeed (response code {response_code})."
        raise SyntheticInputUnavailableError(msg_text)
    if "restore_token" not in results:
        return None
    return cast("str", _unwrap_variant(results["restore_token"]))


def _open_portal_session(restore_token: str | None) -> OpenSessionResult:
    """Real, full CreateSession -> SelectDevices -> Start flow on one connection.

    The one real, untested-by-design (and, uniquely in this repo, not
    even manually verified this pass -- see the module docstring)
    piece of this module. A fresh connection is opened and closed per
    call, matching every other real-D-Bus adapter's own framing.

    Raises:
        SyntheticInputUnavailableError: If any step did not succeed.
    """
    with open_dbus_connection(bus="SESSION") as connection:
        session_handle = _create_session(connection)
        _select_devices(connection, session_handle, restore_token)
        new_restore_token = _start(connection, session_handle)
    return session_handle, new_restore_token


def _notify_keysym(session_handle: str, keysym: int, press: bool) -> None:
    """Real NotifyKeyboardKeysym call -- fire-and-forget, no Request/Response involved.

    The other real, untested-by-design (and not manually verified this
    pass) piece of this module -- see the module docstring. Unlike
    CreateSession/SelectDevices/Start, this is a plain method call with
    no ``out`` parameters and no associated Request object: the portal
    spec defines it as a direct notification, not a permission-gated
    request (the permission was already granted, once, by ``Start``).
    """
    state = _KEY_STATE_PRESSED if press else _KEY_STATE_RELEASED
    with open_dbus_connection(bus="SESSION") as connection:
        msg = new_method_call(
            _PORTAL, "NotifyKeyboardKeysym", "oa{sv}iu", (session_handle, {}, keysym, state)
        )
        connection.send_and_get_reply(msg, timeout=_CALL_TIMEOUT_SECONDS)


class PortalSyntheticInputAdapter:
    """Controls the real RemoteDesktop portal to inject synthetic keyboard events."""

    def __init__(
        self,
        open_portal_session: OpenPortalSessionFn | None = None,
        notify_keysym: NotifyKeysymFn | None = None,
    ) -> None:
        """Store the functions used to actually open a session and send a keysym event.

        Args:
            open_portal_session: Given a restore_token (or None),
                returns ``(session_handle, new_restore_token)``.
                Defaults to a real implementation talking to the
                portal. Overridable for tests -- no I/O happens at
                construction time either way.
            notify_keysym: Given a session_handle, keysym, and press
                flag, sends the real event. Defaults to a real
                implementation. Overridable for tests.
        """
        self._open_portal_session: OpenPortalSessionFn = open_portal_session or _open_portal_session
        self._notify_keysym: NotifyKeysymFn = notify_keysym or _notify_keysym

    def start_session(self, restore_token: str | None) -> SyntheticInputSession:
        """Open (or replay) a RemoteDesktop session, with one automatic fallback on a bad token.

        ADR-0047's own restore_token lifecycle: if ``restore_token`` is
        given but replay fails, falls back to exactly one fresh
        interactive grant attempt (``restore_token=None``) -- never
        retried beyond that. If ``restore_token`` was already ``None``,
        a failure is not retried at all (there is nothing to fall back
        *to*).

        Raises:
            SyntheticInputUnavailableError: If the (possibly retried)
                attempt does not succeed.
        """
        try:
            session_handle, new_token = self._open_portal_session(restore_token)
        except SyntheticInputUnavailableError:
            if restore_token is None:
                raise
            session_handle, new_token = self._open_portal_session(None)
        return SyntheticInputSession(session_handle=session_handle, new_restore_token=new_token)

    def send_keysym(self, session: SyntheticInputSession, keysym: int, *, press: bool) -> None:
        """Fire one real NotifyKeyboardKeysym press or release event."""
        self._notify_keysym(session.session_handle, keysym, press)
