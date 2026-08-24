"""Unit tests for jarvis.adapters.brave.BraveCliAdapter.

What's faked and why: the actual launch (a real subprocess call) is
injected. A real Brave launch is never exercised anywhere in this
suite, deliberately -- see the adapter module's own docstring for why
(opening a real, visible browser window during an unattended run is
exactly the kind of uninvited real-desktop side effect this project's
hard-stop rule exists to avoid). These tests exercise only this
adapter's own dispatch logic: what argv gets built, and how a launch
failure becomes BrowserLaunchFailedError.
"""

from __future__ import annotations

import pytest

from jarvis.adapters.brave import BraveCliAdapter
from jarvis.ports.brave import BrowserLaunchFailedError


def test_open_url_launches_brave_browser_with_the_given_url() -> None:
    """open_url(url) launches exactly ("brave-browser", url), nothing more."""
    calls: list[tuple[str, ...]] = []
    adapter = BraveCliAdapter(launch=calls.append)

    adapter.open_url("https://example.com")

    assert calls == [("brave-browser", "https://example.com")]


def test_a_launch_failure_becomes_browser_launch_failed_error() -> None:
    """An OSError from the injected launch (e.g. binary not found) becomes the port-level error."""

    def failing_launch(_argv: tuple[str, ...]) -> None:
        raise OSError("brave-browser: command not found")

    adapter = BraveCliAdapter(launch=failing_launch)

    with pytest.raises(BrowserLaunchFailedError):
        adapter.open_url("https://example.com")
