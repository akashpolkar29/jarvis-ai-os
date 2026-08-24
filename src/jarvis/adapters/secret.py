"""Adapters implementing jarvis.ports.secret.SecretPort.

:class:`SecretServiceAdapter` talks to whatever secret service is
registered on the session bus via the freedesktop Secret Service API
(https://specifications.freedesktop.org/secret-service/latest/), the
same D-Bus interface GNOME Keyring, KWallet's D-Bus shim, and
KeePassXC's Secret Service integration all implement. There is no new
protocol here, matching ``adapters/media_player.py``'s own framing for
MPRIS -- see ADR-0042 for why this adapter exists at all.

Protocol shape, verified live against a real running ``gnome-keyring-daemon``
on this machine before this adapter was written (not assumed from the
spec alone): ``Service.OpenSession("plain", "")`` returns a session
object path; ``Service.SearchItems({"reference": <reference>})``
searches every collection at once and returns ``(unlocked, locked)``
item-path arrays; ``Service.GetSecrets(unlocked, session)`` returns
each item's ``(session, parameters, value, content_type)`` Secret
struct, whose ``value`` is UTF-8-encoded bytes for the ``text/plain``
secrets this adapter deals in. **A session is scoped to the connection
that opened it** -- confirmed the hard way while first drafting this
adapter, by trying to reuse a session's object path on a second, freshly
opened connection and having ``GetSecrets`` reject it; the real,
manually-verified flow below does ``OpenSession``, ``SearchItems``, and
``GetSecrets`` on one single connection, never split across two. A
reference found only in ``locked`` is treated the same as not found at
all -- see :func:`_find_secret_value`'s docstring for why.

Testability seam, matching ``adapters/media_player.py`` exactly: all
the actual D-Bus wire mechanics live in one small function,
:func:`_search_and_get_secrets`, injectable via the constructor. Unit
tests fake this single function rather than a real bus connection. It
has no automated test of its own: it requires a live D-Bus session bus
and a real Secret Service, exactly what cannot be relied on in CI. Its
correctness is proven by manual verification instead (a real secret
was created, searched for, read back byte-for-byte, and deleted again
against this machine's real gnome-keyring during WP-32).

:meth:`SecretServiceAdapter.set_secret` (ADR-0047, WP-56) writes via
``Collection.CreateItem`` on the default collection's real alias
object path (``/org/freedesktop/secrets/aliases/default`` -- confirmed
live via ``gdbus introspect`` before writing this, not assumed from the
spec: ``CreateItem(properties: a{sv}, secret: (oayays), replace: b) ->
(item: o, prompt: o)``). Matches ``get_secret``'s own testability seam
exactly: the real wire call lives in one small, injectable,
untested-by-design function (:func:`_create_item`); this one *was*
manually verified for real against this machine's live gnome-keyring
before being written up here (a real value was set, read back
byte-for-byte via the existing ``get_secret`` path, overwritten, and
read back again to confirm ``replace=True`` genuinely replaces rather
than duplicates) -- unlike the RemoteDesktop portal calls ADR-0047 also
needed, this one required no interactive dialog, so real, live
verification was safe to do in this pass. ``prompt`` is not acted on:
on this machine's normal, already-unlocked default collection it comes
back as the null object path ``"/"``, matching ``get_secret``'s own
"no ``Prompt``-flow built, not needed on a normal already-unlocked
desktop session" precedent (ADR-0042) -- a real, non-null prompt (a
locked default collection) is not handled here, the same documented gap
``_find_secret_value`` already carries for reads.

:func:`_find_secret_value`, by contrast, is deliberately factored out
as its own pure, I/O-free function specifically so it CAN be unit-
tested directly, with fake search/secrets results, no bus required --
matching ``_unwrap_reply``'s role in ``adapters/media_player.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jeepney import DBusAddress, new_method_call
from jeepney.io.blocking import open_dbus_connection

from jarvis.ports.secret import SecretNotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable

    # item object path -> (session, parameters, value, content_type)
    SecretsByItem = dict[str, tuple[str, bytes, bytes, str]]
    # (unlocked item paths, locked item paths, secrets-by-item for the unlocked ones)
    SearchResult = tuple[list[str], list[str], "SecretsByItem"]
    SearchAndGetSecrets = Callable[[str], SearchResult]
    CreateItem = Callable[[str, str], None]

_SERVICE = DBusAddress(
    object_path="/org/freedesktop/secrets",
    bus_name="org.freedesktop.secrets",
    interface="org.freedesktop.Secret.Service",
)
_DEFAULT_COLLECTION = DBusAddress(
    object_path="/org/freedesktop/secrets/aliases/default",
    bus_name="org.freedesktop.secrets",
    interface="org.freedesktop.Secret.Collection",
)
_CALL_TIMEOUT_SECONDS = 5.0


def _search_and_get_secrets(reference: str) -> SearchResult:
    """Open one session, search for ``reference``, fetch its secrets, all on one connection.

    The one real, untested-by-design piece of this module -- see the
    module docstring for why, including why a session cannot be split
    across two connections. A fresh connection is opened and closed
    per call, matching ``_send_method_call_over_dbus``'s framing in
    ``adapters/media_player.py``: there is no persistent session to
    reuse across calls.
    """
    with open_dbus_connection(bus="SESSION") as connection:
        open_session_msg = new_method_call(_SERVICE, "OpenSession", "sv", ("plain", ("s", "")))
        open_session_reply = connection.send_and_get_reply(
            open_session_msg, timeout=_CALL_TIMEOUT_SECONDS
        )
        _output, session_path = open_session_reply.body

        search_msg = new_method_call(_SERVICE, "SearchItems", "a{ss}", ({"reference": reference},))
        search_reply = connection.send_and_get_reply(search_msg, timeout=_CALL_TIMEOUT_SECONDS)
        unlocked, locked = search_reply.body

        if not unlocked:
            return unlocked, locked, {}

        get_secrets_msg = new_method_call(_SERVICE, "GetSecrets", "aoo", (unlocked, session_path))
        get_secrets_reply = connection.send_and_get_reply(
            get_secrets_msg, timeout=_CALL_TIMEOUT_SECONDS
        )
        secrets: SecretsByItem = get_secrets_reply.body[0]
        return unlocked, locked, secrets


def _create_item(reference: str, value: str) -> None:
    """Open one session and create/replace an item under ``reference`` on the default collection.

    The one real, untested-by-design-by-CI piece of the write path --
    manually verified live against this machine's real gnome-keyring
    instead (see the module docstring). ``OpenSession`` is repeated
    here rather than shared with ``_search_and_get_secrets``, matching
    that function's own "a session is scoped to the connection that
    opened it, never split across two" finding -- this is a second,
    independent connection for a second, independent operation, not an
    optimization opportunity.
    """
    with open_dbus_connection(bus="SESSION") as connection:
        open_session_msg = new_method_call(_SERVICE, "OpenSession", "sv", ("plain", ("s", "")))
        open_session_reply = connection.send_and_get_reply(
            open_session_msg, timeout=_CALL_TIMEOUT_SECONDS
        )
        _output, session_path = open_session_reply.body

        secret_struct = (session_path, b"", value.encode("utf-8"), "text/plain")
        # get_secret() (ADR-0042) resolves via a search keyed on Attributes,
        # not Label -- set here so a value this writes is actually findable
        # by the existing read path, not just visible in a keyring UI.
        properties = {
            "org.freedesktop.Secret.Item.Label": ("s", reference),
            "org.freedesktop.Secret.Item.Attributes": ("a{ss}", {"reference": reference}),
        }
        create_item_msg = new_method_call(
            _DEFAULT_COLLECTION,
            "CreateItem",
            "a{sv}(oayays)b",
            (properties, secret_struct, True),
        )
        connection.send_and_get_reply(create_item_msg, timeout=_CALL_TIMEOUT_SECONDS)


def _find_secret_value(
    reference: str, unlocked: list[str], locked: list[str], secrets: SecretsByItem
) -> str:
    """Return the decoded value of the first unlocked item found for ``reference``.

    Pure and I/O-free -- unit-tested directly with fake ``unlocked``/
    ``locked``/``secrets`` values, no bus required. A ``reference``
    that only turns up in ``locked`` raises :class:`SecretNotFoundError`
    the same as one found nowhere at all: from a caller's perspective
    both mean "the secret this adapter was asked for is not reachable
    right now," and distinguishing them would require the full
    ``Prompt``-object unlock flow ADR-0042 deliberately did not build
    (no real M2 caller needs it on a normal, already-unlocked desktop
    session). ``unlocked`` may list more than one matching item across
    different collections; the first is used, with no further
    selection logic, matching ``_discover_player``'s "whichever is
    found first" framing in ``adapters/media_player.py``.
    """
    if not unlocked:
        msg = f"No secret found for reference {reference!r}" + (
            " (a matching item exists but its collection is locked)." if locked else "."
        )
        raise SecretNotFoundError(msg)
    _session, _parameters, value, _content_type = secrets[unlocked[0]]
    return value.decode("utf-8")


class SecretServiceAdapter:
    """Resolves secret references against whatever Secret Service is on the session bus."""

    def __init__(
        self,
        search_and_get_secrets: SearchAndGetSecrets | None = None,
        create_item: CreateItem | None = None,
    ) -> None:
        """Store the functions used to actually search/fetch and create/replace secrets.

        Args:
            search_and_get_secrets: Given a reference, returns
                ``(unlocked, locked, secrets)``. Defaults to a real
                implementation talking to the session bus. Overridable
                for tests, matching ``MprisMediaPlayerAdapter``'s
                ``send_method_call`` constructor argument -- no I/O
                happens at construction time either way.
            create_item: Given a reference and a value, creates or
                replaces the corresponding item on the default
                collection. Defaults to a real implementation talking
                to the session bus. Overridable for tests, same
                reasoning as ``search_and_get_secrets``.
        """
        self._search_and_get_secrets: SearchAndGetSecrets = (
            search_and_get_secrets or _search_and_get_secrets
        )
        self._create_item: CreateItem = create_item or _create_item

    def get_secret(self, reference: str) -> str:
        """Resolve ``reference`` to its real secret value.

        Raises:
            SecretNotFoundError: If no unlocked secret matches ``reference``.
        """
        unlocked, locked, secrets = self._search_and_get_secrets(reference)
        return _find_secret_value(reference, unlocked, locked, secrets)

    def set_secret(self, reference: str, value: str) -> None:
        """Store ``value`` under ``reference`` on the default collection, creating or replacing."""
        self._create_item(reference, value)
