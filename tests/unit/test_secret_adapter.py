"""Unit tests for jarvis.adapters.secret.SecretServiceAdapter.

What's mocked and why: only the actual D-Bus wire I/O
(``search_and_get_secrets``) is faked -- no real session bus or Secret
Service is required, or reliably available, in CI. Everything these
tests exercise is this adapter's own matching logic: which item it
picks when more than one is unlocked, that a locked-only match is
treated as not found, and that the secret's raw bytes are decoded as
UTF-8. The low-level jeepney plumbing this fake stands in for
(``_search_and_get_secrets``) has no automated test -- see
adapters/secret.py's module docstring for why -- and is proven correct
by manual verification instead (a real secret was created, resolved,
and deleted against this machine's real gnome-keyring during WP-32).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.secret import SecretServiceAdapter, _create_item, _find_secret_value
from jarvis.ports.secret import SecretNotFoundError

if TYPE_CHECKING:
    _SecretsByItem = dict[str, tuple[str, bytes, bytes, str]]
    _SearchResult = tuple[list[str], list[str], _SecretsByItem]


def test_get_secret_returns_the_decoded_value_of_the_only_unlocked_match() -> None:
    def fake_search(reference: str) -> _SearchResult:
        assert reference == "family-a-api-key"
        secrets = {"/item/1": ("/session/1", b"", b"sk-real-value", "text/plain")}
        return ["/item/1"], [], secrets

    adapter = SecretServiceAdapter(fake_search)

    assert adapter.get_secret("family-a-api-key") == "sk-real-value"


def test_get_secret_picks_the_first_unlocked_item_when_more_than_one_matches() -> None:
    def fake_search(_reference: str) -> _SearchResult:
        secrets = {
            "/item/1": ("/session/1", b"", b"first", "text/plain"),
            "/item/2": ("/session/1", b"", b"second", "text/plain"),
        }
        return ["/item/1", "/item/2"], [], secrets

    adapter = SecretServiceAdapter(fake_search)

    assert adapter.get_secret("ambiguous-reference") == "first"


def test_get_secret_raises_secret_not_found_when_nothing_matches() -> None:
    def fake_search(_reference: str) -> _SearchResult:
        return [], [], {}

    adapter = SecretServiceAdapter(fake_search)

    with pytest.raises(SecretNotFoundError, match="no-such-reference"):
        adapter.get_secret("no-such-reference")


def test_get_secret_raises_secret_not_found_when_the_only_match_is_locked() -> None:
    """A locked-only match is indistinguishable from "not found" -- see the port docstring."""

    def fake_search(_reference: str) -> _SearchResult:
        return [], ["/item/1"], {}

    adapter = SecretServiceAdapter(fake_search)

    with pytest.raises(SecretNotFoundError, match="locked"):
        adapter.get_secret("locked-reference")


def test_find_secret_value_is_directly_testable_with_no_bus() -> None:
    """The pure matching function used by get_secret needs no fake adapter to exercise."""
    secrets = {"/item/1": ("/session/1", b"", b"value-bytes", "text/plain")}

    assert _find_secret_value("ref", ["/item/1"], [], secrets) == "value-bytes"


def test_set_secret_calls_create_item_with_the_reference_and_value() -> None:
    """set_secret's own dispatch logic: it delegates to the injected create_item verbatim."""
    calls: list[tuple[str, str]] = []

    def fake_create_item(reference: str, value: str) -> None:
        calls.append((reference, value))

    adapter = SecretServiceAdapter(create_item=fake_create_item)

    adapter.set_secret("synthetic-input.restore-token", "token-value")

    assert calls == [("synthetic-input.restore-token", "token-value")]


def test_set_secret_default_create_item_is_the_real_dbus_implementation() -> None:
    """No fake given -- set_secret dispatches to the real, untested-by-design _create_item."""
    adapter = SecretServiceAdapter()

    assert adapter._create_item is _create_item
