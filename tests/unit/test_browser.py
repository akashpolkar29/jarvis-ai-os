"""Unit tests for jarvis.domain.browser.PageHandle."""

from __future__ import annotations

import pytest

from jarvis.domain.browser import PageHandle


def test_page_handle_stores_all_three_fields() -> None:
    """A valid PageHandle stores debug_port/target_id/process_id unchanged."""
    handle = PageHandle(debug_port=9222, target_id="abc-123", process_id=4242)

    assert handle.debug_port == 9222
    assert handle.target_id == "abc-123"
    assert handle.process_id == 4242


def test_page_handle_rejects_a_non_positive_debug_port() -> None:
    """A zero or negative debug_port is rejected at construction time."""
    with pytest.raises(ValueError, match="debug_port must be positive"):
        PageHandle(debug_port=0, target_id="abc-123", process_id=4242)


def test_page_handle_rejects_an_empty_target_id() -> None:
    """An empty target_id is rejected at construction time."""
    with pytest.raises(ValueError, match="target_id must not be empty"):
        PageHandle(debug_port=9222, target_id="", process_id=4242)


def test_page_handle_rejects_a_non_positive_process_id() -> None:
    """A zero or negative process_id is rejected at construction time."""
    with pytest.raises(ValueError, match="process_id must be positive"):
        PageHandle(debug_port=9222, target_id="abc-123", process_id=0)
