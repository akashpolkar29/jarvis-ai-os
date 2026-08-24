"""Unit tests for jarvis.kernel.desktop's authorize_and_* composition-root functions.

What's mocked and why: small stub ports (with call tracking) are
injected in place of real adapters (BraveCliAdapter, VsCodeCliAdapter),
for the same reason kernel/music.py's own tests inject a stub
MediaPlayerPort -- these tests must be hermetic and never launch a
real, visible browser or editor window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.kernel.desktop import authorize_and_open_brave_url, authorize_and_open_vscode_file
from jarvis.ports.brave import BrowserLaunchFailedError
from jarvis.ports.vscode import EditorLaunchFailedError

if TYPE_CHECKING:
    from pathlib import Path

_GRANTED_CALLS = 1


class _StubBrowser:
    """A BravePort test double that records which URLs were opened, in order."""

    def __init__(self, *, raise_on_call: bool = False) -> None:
        """Start with an empty call log; optionally raise BrowserLaunchFailedError on any call."""
        self.calls: list[str] = []
        self._raise_on_call = raise_on_call

    def open_url(self, url: str) -> None:
        """Record an open_url() call."""
        self.calls.append(url)
        if self._raise_on_call:
            msg = "Failed to launch brave-browser: not found"
            raise BrowserLaunchFailedError(msg)


def test_granted_call_opens_the_url(tmp_path: Path) -> None:
    """A granted call (confirmation flag set) calls open_url with exactly the given URL."""
    browser = _StubBrowser()

    decision = authorize_and_open_brave_url(
        "https://example.com",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        browser=browser,
    )

    assert decision.granted is True
    assert browser.calls == ["https://example.com"]


def test_denied_call_never_touches_the_browser(tmp_path: Path) -> None:
    """With no confirmation flags, CONFIRM-tier desktop.brave_open_url is denied, browser untouched.

    This is the same enforcement-ordering guarantee kernel/music.py's
    own tests prove: authorization happens before any real side effect.
    """
    browser = _StubBrowser()

    decision = authorize_and_open_brave_url(
        "https://example.com",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        browser=browser,
    )

    assert decision.granted is False
    assert browser.calls == []


def test_remote_confirmation_alone_is_sufficient_to_grant(tmp_path: Path) -> None:
    """CONFIRM tier grants on physical OR remote confirmation -- remote alone is enough."""
    browser = _StubBrowser()

    decision = authorize_and_open_brave_url(
        "https://example.com",
        physical_confirmation_available=False,
        remote_confirmation_available=True,
        chain_path=tmp_path / "audit_chain.json",
        browser=browser,
    )

    assert decision.granted is True
    assert browser.calls == ["https://example.com"]


def test_a_single_granted_call_appends_one_verifiable_record(tmp_path: Path) -> None:
    """One authorize_and_open_brave_url() call persists exactly one record that verifies."""
    chain_path = tmp_path / "audit_chain.json"

    authorize_and_open_brave_url(
        "https://example.com",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        browser=_StubBrowser(),
    )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == _GRANTED_CALLS
    assert chain.verify().valid is True


def test_audit_record_is_saved_even_when_the_browser_raises(tmp_path: Path) -> None:
    """A granted decision is persisted even if the subsequent real-world action fails.

    This is the try/finally audit-save guarantee: without it, a
    BrowserLaunchFailedError raised after authorize_by_id() already
    appended the record in-memory would cause storage.save() to be
    skipped, silently losing that record from disk.
    """
    chain_path = tmp_path / "audit_chain.json"
    browser = _StubBrowser(raise_on_call=True)

    with pytest.raises(BrowserLaunchFailedError):
        authorize_and_open_brave_url(
            "https://example.com",
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=chain_path,
            browser=browser,
        )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == _GRANTED_CALLS
    assert chain[0].decision.granted is True


class _StubEditor:
    """A VsCodePort test double that records which paths were opened, in order."""

    def __init__(self, *, raise_on_call: bool = False) -> None:
        """Start with an empty call log; optionally raise EditorLaunchFailedError on any call."""
        self.calls: list[str] = []
        self._raise_on_call = raise_on_call

    def open_file(self, path: str) -> None:
        """Record an open_file() call."""
        self.calls.append(path)
        if self._raise_on_call:
            msg = "Failed to launch code: not found"
            raise EditorLaunchFailedError(msg)


def test_granted_vscode_call_opens_the_file(tmp_path: Path) -> None:
    """A granted call (confirmation flag set) calls open_file with exactly the given path."""
    editor = _StubEditor()

    decision = authorize_and_open_vscode_file(
        "/home/user/project/main.py",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        editor=editor,
    )

    assert decision.granted is True
    assert editor.calls == ["/home/user/project/main.py"]


def test_denied_vscode_call_never_touches_the_editor(tmp_path: Path) -> None:
    """No confirmation flags: CONFIRM-tier desktop.vscode_open_file is denied, editor untouched."""
    editor = _StubEditor()

    decision = authorize_and_open_vscode_file(
        "/home/user/project/main.py",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        editor=editor,
    )

    assert decision.granted is False
    assert editor.calls == []


def test_vscode_audit_record_is_saved_even_when_the_editor_raises(tmp_path: Path) -> None:
    """A granted decision is persisted even if the subsequent real-world action fails."""
    chain_path = tmp_path / "audit_chain.json"
    editor = _StubEditor(raise_on_call=True)

    with pytest.raises(EditorLaunchFailedError):
        authorize_and_open_vscode_file(
            "/home/user/project/main.py",
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=chain_path,
            editor=editor,
        )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == _GRANTED_CALLS
    assert chain[0].decision.granted is True
