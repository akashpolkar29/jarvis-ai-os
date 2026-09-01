"""Unit tests for jarvis.domain.browser.PageHandle."""

from __future__ import annotations

import pytest

from jarvis.domain.browser import PageHandle

_DEBUG_PORT = 9222
_PROCESS_ID = 4242


def test_page_handle_stores_all_four_fields() -> None:
    """A valid PageHandle stores debug_port/target_id/process_id/user_data_dir unchanged."""
    handle = PageHandle(
        debug_port=_DEBUG_PORT,
        target_id="abc-123",
        process_id=_PROCESS_ID,
        user_data_dir="/tmp/jarvis-x",
    )

    assert handle.debug_port == _DEBUG_PORT
    assert handle.target_id == "abc-123"
    assert handle.process_id == _PROCESS_ID
    assert handle.user_data_dir == "/tmp/jarvis-x"


def test_page_handle_rejects_a_non_positive_debug_port() -> None:
    """A zero or negative debug_port is rejected at construction time."""
    with pytest.raises(ValueError, match="debug_port must be positive"):
        PageHandle(debug_port=0, target_id="abc-123", process_id=4242, user_data_dir="/tmp/x")


def test_page_handle_rejects_an_empty_target_id() -> None:
    """An empty target_id is rejected at construction time."""
    with pytest.raises(ValueError, match="target_id must not be empty"):
        PageHandle(debug_port=9222, target_id="", process_id=4242, user_data_dir="/tmp/x")


def test_page_handle_rejects_a_non_positive_process_id() -> None:
    """A zero or negative process_id is rejected at construction time."""
    with pytest.raises(ValueError, match="process_id must be positive"):
        PageHandle(debug_port=9222, target_id="abc-123", process_id=0, user_data_dir="/tmp/x")


def test_page_handle_rejects_an_empty_user_data_dir() -> None:
    """An empty user_data_dir is rejected at construction time."""
    with pytest.raises(ValueError, match="user_data_dir must not be empty"):
        PageHandle(debug_port=9222, target_id="abc-123", process_id=4242, user_data_dir="")
