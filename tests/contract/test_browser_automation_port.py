"""Contract test: jarvis.ports.browser_automation.BrowserAutomationPort's own shape.

A minimal fake proves the Protocol itself is well-formed and
satisfiable independent of any specific adapter (M3's own "port exists
and is tested structurally before any real technology is chosen"
ordering, followed again here for M5's browser-automation track). The
real CDP-backed adapter (WP-68) is checked separately, in
``tests/unit/adapters/test_browser_automation.py``.
"""

from __future__ import annotations

from jarvis.domain.browser import PageHandle
from jarvis.ports.browser_automation import BrowserAutomationPort

_FAKE_HANDLE = PageHandle(debug_port=9222, target_id="fake-target", process_id=1)


class _FakeBrowserAutomationAdapter:
    """A minimal, real fake proving BrowserAutomationPort is satisfiable."""

    async def open_page(self, url: str) -> PageHandle:  # noqa: ARG002
        return _FAKE_HANDLE

    async def capture_screenshot(self, handle: PageHandle) -> bytes:  # noqa: ARG002
        return b"\x89PNG\r\n\x1a\n"

    async def query_dom(self, handle: PageHandle, selector: str) -> str | None:  # noqa: ARG002
        return "<div></div>"

    async def close(self, handle: PageHandle) -> None:
        pass


def test_a_conforming_fake_satisfies_browser_automation_port() -> None:
    """A real, minimal implementation is structurally a BrowserAutomationPort."""
    adapter = _FakeBrowserAutomationAdapter()

    assert isinstance(adapter, BrowserAutomationPort)


def test_an_object_missing_the_required_methods_does_not_satisfy_browser_automation_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotABrowserAutomationSource:
        """Deliberately lacks open_page()/capture_screenshot()/query_dom()/close()."""

    assert isinstance(NotABrowserAutomationSource(), BrowserAutomationPort) is False
