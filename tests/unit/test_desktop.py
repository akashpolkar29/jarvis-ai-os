"""Unit tests for jarvis.domain.desktop.WindowHandle and SyntheticInputSession."""

from __future__ import annotations

import pytest

from jarvis.domain.desktop import SyntheticInputSession, WindowHandle


def test_window_handle_stores_value_and_app_id() -> None:
    """A valid WindowHandle stores both fields unchanged."""
    handle = WindowHandle(value="code:12345", app_id="code")

    assert handle.value == "code:12345"
    assert handle.app_id == "code"


def test_window_handle_rejects_an_empty_value() -> None:
    """An empty value is rejected at construction time."""
    with pytest.raises(ValueError, match="value must not be empty"):
        WindowHandle(value="", app_id="code")


def test_window_handle_rejects_an_empty_app_id() -> None:
    """An empty app_id is rejected at construction time."""
    with pytest.raises(ValueError, match="app_id must not be empty"):
        WindowHandle(value="code:12345", app_id="")


def test_synthetic_input_session_stores_session_handle_and_new_restore_token() -> None:
    """A valid SyntheticInputSession stores both fields unchanged -- ADR-0047."""
    session = SyntheticInputSession(session_handle="/session/1", new_restore_token="tok")

    assert session.session_handle == "/session/1"
    assert session.new_restore_token == "tok"


def test_synthetic_input_session_allows_a_none_new_restore_token() -> None:
    """No new/rotated token is a real, valid outcome -- not every session issues one."""
    session = SyntheticInputSession(session_handle="/session/1", new_restore_token=None)

    assert session.new_restore_token is None


def test_synthetic_input_session_rejects_an_empty_session_handle() -> None:
    """An empty session_handle is rejected at construction time."""
    with pytest.raises(ValueError, match="session_handle must not be empty"):
        SyntheticInputSession(session_handle="", new_restore_token=None)
