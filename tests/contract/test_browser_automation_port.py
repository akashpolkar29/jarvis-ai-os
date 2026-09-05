"""Contract test: jarvis.ports.browser_automation.BrowserAutomationPort's own shape.

A minimal fake proves the Protocol itself is well-formed and
satisfiable independent of any specific adapter (M3's own "port exists
and is tested structurally before any real technology is chosen"
ordering, followed again here for M5's browser-automation track).

**Real gap found and closed (10-phase combined pass, Phase 10, adapter-
contract-validation task)**: this file's own docstring used to claim
the real CDP-backed adapter was "checked separately, in
tests/unit/adapters/test_browser_automation.py" -- confirmed false by
direct inspection: that file never once references
``BrowserAutomationPort`` or performs an ``isinstance`` check.
``CdpBrowserAutomationAdapter`` had never actually been structurally
proven to satisfy this Protocol anywhere in the test suite, only
behaviorally exercised -- a silent method rename/signature drift could
have gone uncaught by any Protocol-conformance check. Fixed here,
matching ``tests/contract/test_reasoning_port.py``'s own established
"every real adapter checked in the same contract file" precedent.
"""

from __future__ import annotations

from jarvis.adapters.browser_automation import CdpBrowserAutomationAdapter
from jarvis.domain.browser import PageHandle
from jarvis.ports.browser_automation import BrowserAutomationPort

_FAKE_HANDLE = PageHandle(
    debug_port=9222, target_id="fake-target", process_id=1, user_data_dir="/tmp/fake-profile"
)


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


def test_cdp_browser_automation_adapter_satisfies_browser_automation_port() -> None:
    """The real, production CDP-backed adapter (WP-68) is structurally a BrowserAutomationPort.

    Construction alone does no I/O (see the adapter's own docstring),
    so this is a pure, real Protocol-conformance check -- no real
    browser process or CDP connection involved.
    """
    adapter = CdpBrowserAutomationAdapter()

    assert isinstance(adapter, BrowserAutomationPort)
