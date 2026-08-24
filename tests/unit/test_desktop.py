"""Unit tests for jarvis.domain.desktop.WindowHandle."""

from __future__ import annotations

import pytest

from jarvis.domain.desktop import WindowHandle


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
