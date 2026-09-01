"""Unit tests for jarvis.kernel.browser's authorize_and_* composition-root functions.

A stub BrowserAutomationPort (with call tracking) is injected in place
of the real CdpBrowserAutomationAdapter, for the same reason
test_desktop_kernel.py's own _StubBrowser is injected in place of
BraveCliAdapter -- these tests must be hermetic and never launch a
real browser subprocess.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.domain.browser import PageHandle
from jarvis.kernel.browser import (
    authorize_and_capture_screenshot,
    authorize_and_open_page,
    authorize_and_query_dom,
    close_browser_page,
)
from jarvis.ports.browser_automation import BrowserActionFailedError, BrowserLaunchFailedError

if TYPE_CHECKING:
    from pathlib import Path

_GRANTED_CALLS = 1
_FAKE_HANDLE = PageHandle(
    debug_port=9222, target_id="target-abc", process_id=1234, user_data_dir="/tmp/fake-profile"
)


class _StubBrowserAutomation:
    """A BrowserAutomationPort test double that records every call, in order."""

    def __init__(self, *, raise_on_open: bool = False) -> None:
        self.opened: list[str] = []
        self.screenshotted: list[PageHandle] = []
        self.queried: list[tuple[PageHandle, str]] = []
        self.closed: list[PageHandle] = []
        self._raise_on_open = raise_on_open

    async def open_page(self, url: str) -> PageHandle:
        self.opened.append(url)
        if self._raise_on_open:
            msg = "Failed to launch brave-browser: not found"
            raise BrowserLaunchFailedError(msg)
        return _FAKE_HANDLE

    async def capture_screenshot(self, handle: PageHandle) -> bytes:
        self.screenshotted.append(handle)
        return b"\x89PNG\r\n\x1a\nfake"

    async def query_dom(self, handle: PageHandle, selector: str) -> str | None:
        self.queried.append((handle, selector))
        return "<div>hi</div>" if selector == "#marker" else None

    async def close(self, handle: PageHandle) -> None:
        self.closed.append(handle)


async def test_granted_open_page_opens_the_real_url(tmp_path: Path) -> None:
    browser = _StubBrowserAutomation()

    decision, handle = await authorize_and_open_page(
        "https://example.com",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        browser_automation=browser,
    )

    assert decision.granted is True
    assert browser.opened == ["https://example.com"]
    assert handle == _FAKE_HANDLE


async def test_denied_open_page_never_touches_the_browser(tmp_path: Path) -> None:
    browser = _StubBrowserAutomation()

    decision, handle = await authorize_and_open_page(
        "https://example.com",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        browser_automation=browser,
    )

    assert decision.granted is False
    assert browser.opened == []
    assert handle is None


async def test_remote_confirmation_alone_is_sufficient_to_grant_open_page(tmp_path: Path) -> None:
    browser = _StubBrowserAutomation()

    decision, handle = await authorize_and_open_page(
        "https://example.com",
        physical_confirmation_available=False,
        remote_confirmation_available=True,
        chain_path=tmp_path / "audit_chain.json",
        browser_automation=browser,
    )

    assert decision.granted is True
    assert handle == _FAKE_HANDLE


async def test_a_single_granted_open_page_appends_one_verifiable_record(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"

    await authorize_and_open_page(
        "https://example.com",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        browser_automation=_StubBrowserAutomation(),
    )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == _GRANTED_CALLS
    assert chain.verify().valid is True


async def test_audit_record_is_saved_even_when_open_page_raises(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"
    browser = _StubBrowserAutomation(raise_on_open=True)

    with pytest.raises(BrowserLaunchFailedError):
        await authorize_and_open_page(
            "https://example.com",
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=chain_path,
            browser_automation=browser,
        )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == _GRANTED_CALLS
    assert chain[0].decision.granted is True


async def test_granted_screenshot_captures_and_tags_real_content(tmp_path: Path) -> None:
    browser = _StubBrowserAutomation()

    decision, screenshot = await authorize_and_capture_screenshot(
        _FAKE_HANDLE,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        browser_automation=browser,
    )

    assert decision.granted is True
    assert browser.screenshotted == [_FAKE_HANDLE]
    assert screenshot is not None
    assert screenshot.value == b"\x89PNG\r\n\x1a\nfake"
    assert screenshot.provenance.classification.name == "SENSITIVE"
    assert screenshot.provenance.is_tainted is True


async def test_screenshot_is_always_granted_egress_local_is_allow_tier(tmp_path: Path) -> None:
    """browser.screenshot is EGRESS_LOCAL/ALLOW -- granted regardless of confirmation flags."""
    browser = _StubBrowserAutomation()

    decision, screenshot = await authorize_and_capture_screenshot(
        _FAKE_HANDLE,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        browser_automation=browser,
    )

    assert decision.granted is True
    assert screenshot is not None


async def test_granted_query_dom_returns_tagged_html_when_matched(tmp_path: Path) -> None:
    browser = _StubBrowserAutomation()

    decision, html = await authorize_and_query_dom(
        _FAKE_HANDLE,
        "#marker",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        browser_automation=browser,
    )

    assert decision.granted is True
    assert browser.queried == [(_FAKE_HANDLE, "#marker")]
    assert html is not None
    assert html.value == "<div>hi</div>"
    assert html.provenance.classification.name == "SENSITIVE"


async def test_granted_query_dom_returns_none_when_nothing_matches(tmp_path: Path) -> None:
    browser = _StubBrowserAutomation()

    decision, html = await authorize_and_query_dom(
        _FAKE_HANDLE,
        "#does-not-exist",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        browser_automation=browser,
    )

    assert decision.granted is True
    assert html is None


async def test_query_dom_propagates_a_real_action_failure(tmp_path: Path) -> None:
    class _FailingBrowserAutomation(_StubBrowserAutomation):
        async def query_dom(self, handle: PageHandle, selector: str) -> str | None:  # noqa: ARG002
            msg = "CDP connection lost"
            raise BrowserActionFailedError(msg)

    with pytest.raises(BrowserActionFailedError):
        await authorize_and_query_dom(
            _FAKE_HANDLE,
            "#marker",
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=tmp_path / "audit_chain.json",
            browser_automation=_FailingBrowserAutomation(),
        )


async def test_close_browser_page_calls_the_real_port_close() -> None:
    browser = _StubBrowserAutomation()

    await close_browser_page(_FAKE_HANDLE, browser)

    assert browser.closed == [_FAKE_HANDLE]
