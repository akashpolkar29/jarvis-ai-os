"""Unit tests for jarvis.adapters.vscode.VsCodeCliAdapter.

What's faked and why: see tests/unit/adapters/test_brave.py's own
docstring -- identical reasoning, a real editor launch is never
exercised in this suite.
"""

from __future__ import annotations

import pytest

from jarvis.adapters.vscode import VsCodeCliAdapter
from jarvis.ports.vscode import EditorLaunchFailedError


def test_open_file_launches_code_with_the_given_path() -> None:
    """open_file(path) launches exactly ("code", path), nothing more."""
    calls: list[tuple[str, ...]] = []
    adapter = VsCodeCliAdapter(launch=calls.append)

    adapter.open_file("/home/user/project/main.py")

    assert calls == [("code", "/home/user/project/main.py")]


def test_a_launch_failure_becomes_editor_launch_failed_error() -> None:
    """An OSError from the injected launch (e.g. binary not found) becomes the port-level error."""

    def failing_launch(_argv: tuple[str, ...]) -> None:
        raise OSError("code: command not found")

    adapter = VsCodeCliAdapter(launch=failing_launch)

    with pytest.raises(EditorLaunchFailedError):
        adapter.open_file("/home/user/project/main.py")
