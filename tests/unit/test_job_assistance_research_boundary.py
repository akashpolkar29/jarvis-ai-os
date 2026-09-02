"""Real tests for m6b-job-assistance.md's own acceptance criterion 6: research's real boundary.

"A real test proves browser.open_page is the real, only action taken
when a job posting's own application page is relevant -- no further
capability is ever invoked past opening the page." Two real,
complementary proofs:

1. A structural check: `application/job_assistance/` contains no
   research-orchestration module at all -- the design doc's own item-6
   resolution (mirroring M6a's identical answer) means there is no
   job_assistance-specific research code to invoke anything beyond
   `browser.open_page` with in the first place.
2. A real, direct call to `kernel.browser.authorize_and_open_page` --
   the actual, real action a future job-posting-research flow takes --
   proving the injected `BrowserAutomationPort`'s own `open_page` is
   the only method ever called; `query_dom`/`capture_screenshot`/
   `close` are never reached, structurally proving nothing beyond
   opening the page happens.
"""

from __future__ import annotations

from pathlib import Path

from jarvis.domain.browser import PageHandle
from jarvis.kernel.browser import authorize_and_open_page

_REPO_ROOT = Path(__file__).resolve().parents[2]
_JOB_ASSISTANCE_PACKAGE = _REPO_ROOT / "src" / "jarvis" / "application" / "job_assistance"
_FAKE_HANDLE = PageHandle(
    debug_port=9222, target_id="target-abc", process_id=1234, user_data_dir="/tmp/fake-profile"
)


class _StubConsole:
    def show_line(self, text: str) -> None:
        del text


class _StubBrowserAutomation:
    """Records every call made to it, in order -- across every real method on the port."""

    def __init__(self) -> None:
        self.opened: list[str] = []
        self.screenshotted: list[PageHandle] = []
        self.queried: list[tuple[PageHandle, str]] = []
        self.closed: list[PageHandle] = []

    async def open_page(self, url: str) -> PageHandle:
        self.opened.append(url)
        return _FAKE_HANDLE

    async def capture_screenshot(self, handle: PageHandle) -> bytes:
        self.screenshotted.append(handle)
        return b""

    async def query_dom(self, handle: PageHandle, selector: str) -> str | None:
        self.queried.append((handle, selector))
        return None

    async def close(self, handle: PageHandle) -> None:
        self.closed.append(handle)


def test_no_research_orchestration_module_exists_under_job_assistance() -> None:
    """No application/job_assistance/research.py (or equivalent) was speculatively created.

    Mirrors m6a-communications.md's own item-6 resolution exactly:
    research needs no new port, no new capability, and (checked here,
    not assumed) no new application-layer module either -- a future
    job-posting-research flow calls kernel.browser's already-Accepted
    capabilities directly, the same way M6a's own research does.
    """
    real_modules = {path.name for path in _JOB_ASSISTANCE_PACKAGE.glob("*.py")}

    assert real_modules == {"__init__.py", "classification.py", "drafting.py"}


async def test_opening_a_job_posting_application_page_calls_only_open_page(
    tmp_path: Path,
) -> None:
    """The real, only action taken for a job's own application page is browser.open_page.

    Exercises kernel.browser.authorize_and_open_page directly -- the
    real, already-registered, already-Accepted capability a future
    job-posting-research flow uses, with no job_assistance-specific
    wrapper needed. Proves structurally that opening the page is the
    entire action: every other real method this port exposes
    (query_dom/capture_screenshot/close) is never called.
    """
    browser = _StubBrowserAutomation()

    decision, handle = await authorize_and_open_page(
        "https://example.com/careers/apply/123",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        browser_automation=browser,
        console=_StubConsole(),
    )

    assert decision.granted is True
    assert handle is not None
    assert browser.opened == ["https://example.com/careers/apply/123"]
    assert browser.queried == []
    assert browser.screenshotted == []
    assert browser.closed == []
