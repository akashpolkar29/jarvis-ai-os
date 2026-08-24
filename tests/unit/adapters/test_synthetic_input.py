"""Unit tests for jarvis.adapters.synthetic_input.PortalSyntheticInputAdapter.

What's faked and why: both real D-Bus wire entry points
(``open_portal_session``, ``notify_keysym``) are injected fakes -- a
real RemoteDesktop portal call pops a real, interactive OS permission
dialog, which no automated test may trigger (see the adapter module's
own docstring for the full reasoning, including why this is the one
real-D-Bus adapter in this repo whose wire mechanics were not even
manually verified this pass). Everything these tests exercise is this
adapter's own dispatch logic: the one-automatic-fallback-on-a-bad-token
control flow ADR-0047 specifies, and that send_keysym relays its
arguments unchanged.

``_unwrap_variant``/``_decode_response`` are pure and tested directly,
with no fake adapter needed, matching ``_find_secret_value``'s own role
in ``adapters/secret.py``.
"""

from __future__ import annotations

import pytest

from jarvis.adapters.synthetic_input import (
    PortalSyntheticInputAdapter,
    _decode_response,
    _unwrap_variant,
)
from jarvis.domain.desktop import SyntheticInputSession
from jarvis.ports.synthetic_input import SyntheticInputUnavailableError


def test_start_session_returns_the_session_from_a_successful_first_attempt() -> None:
    """No retry needed: the first attempt succeeding is relayed straight through."""
    adapter = PortalSyntheticInputAdapter(
        open_portal_session=lambda _token: ("/session/1", "new-token")
    )

    session = adapter.start_session(None)

    assert session == SyntheticInputSession(
        session_handle="/session/1", new_restore_token="new-token"
    )


def test_start_session_with_no_token_does_not_retry_on_failure() -> None:
    """No restore_token was given, so there is nothing to fall back to -- fails immediately."""
    calls: list[str | None] = []

    def failing(token: str | None) -> tuple[str, str | None]:
        calls.append(token)
        msg = "denied"
        raise SyntheticInputUnavailableError(msg)

    adapter = PortalSyntheticInputAdapter(open_portal_session=failing)

    with pytest.raises(SyntheticInputUnavailableError):
        adapter.start_session(None)

    assert calls == [None]


def test_start_session_falls_back_to_a_fresh_grant_when_replay_fails() -> None:
    """A stale/invalid restore_token triggers exactly one automatic fallback attempt."""
    calls: list[str | None] = []

    def sometimes_failing(token: str | None) -> tuple[str, str | None]:
        calls.append(token)
        if token is not None:
            msg = "stale token"
            raise SyntheticInputUnavailableError(msg)
        return "/session/2", "fresh-token"

    adapter = PortalSyntheticInputAdapter(open_portal_session=sometimes_failing)

    session = adapter.start_session("stale-token")

    assert calls == ["stale-token", None]
    assert session == SyntheticInputSession(
        session_handle="/session/2", new_restore_token="fresh-token"
    )


def test_start_session_does_not_retry_beyond_the_one_fallback_attempt() -> None:
    """The fresh-grant fallback also failing (e.g. the human denies it) is a hard failure."""
    calls: list[str | None] = []

    def always_failing(token: str | None) -> tuple[str, str | None]:
        calls.append(token)
        msg = "denied"
        raise SyntheticInputUnavailableError(msg)

    adapter = PortalSyntheticInputAdapter(open_portal_session=always_failing)

    with pytest.raises(SyntheticInputUnavailableError):
        adapter.start_session("stale-token")

    assert calls == ["stale-token", None]


def test_send_keysym_relays_session_keysym_and_press_to_notify_keysym() -> None:
    """send_keysym's own dispatch logic: it delegates to the injected notify_keysym verbatim."""
    calls: list[tuple[str, int, bool]] = []
    adapter = PortalSyntheticInputAdapter(
        open_portal_session=lambda _t: ("/session/1", None),
        notify_keysym=lambda session_handle, keysym, press: calls.append(
            (session_handle, keysym, press)
        ),
    )
    session = adapter.start_session(None)

    adapter.send_keysym(session, 97, press=True)
    adapter.send_keysym(session, 97, press=False)

    assert calls == [("/session/1", 97, True), ("/session/1", 97, False)]


def test_unwrap_variant_returns_the_real_value_discarding_the_signature() -> None:
    """Pure, directly testable: jeepney decodes a{sv} entries as (signature, value) tuples."""
    assert _unwrap_variant(("s", "/org/freedesktop/portal/desktop/session/1")) == (
        "/org/freedesktop/portal/desktop/session/1"
    )
    assert _unwrap_variant(("u", 1)) == 1


def test_decode_response_splits_response_code_and_results() -> None:
    """Pure, directly testable: a Response signal's body is (response_code, results)."""
    code, results = _decode_response((0, {"session_handle": ("s", "/session/1")}))

    assert code == 0
    assert results == {"session_handle": ("s", "/session/1")}
