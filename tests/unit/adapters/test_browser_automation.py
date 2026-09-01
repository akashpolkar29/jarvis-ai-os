"""Unit tests for jarvis.adapters.browser_automation.CdpBrowserAutomationAdapter.

Fully hermetic: the real subprocess-launch and real WebSocket-connect
seams are both injected with fakes throughout (mirroring
``adapters/brave.py``'s own ``launch``-injection precedent), so no
real ``brave-browser`` process or real network socket is ever touched
here -- this exercises the adapter's own real dispatch logic (which
argv is built, which CDP messages are sent, how a real response is
parsed) only.

The one real, live, end-to-end proof this work package's own design
doc calls for -- "given a real URL, open the page... capture one real
screenshot and one real DOM query" -- lives in
``test_real_cdp_flow_against_a_local_page`` below, guarded by a real
``skipif`` on the real ``brave-browser`` binary's own presence,
mirroring ``tests/unit/adapters/test_sandbox.py``'s own real-GUI-test
precedent exactly: live-verified on this real development machine, not
merely asserted, and honestly skipped (not weakened) on CI, which does
not install that binary (confirmed: ``.github/workflows/ci.yml``).
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.browser_automation import (
    CdpBrowserAutomationAdapter,
    _wait_for_devtools_active_port,
)
from jarvis.domain.browser import PageHandle
from jarvis.ports.browser_automation import BrowserActionFailedError, BrowserLaunchFailedError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from jarvis.adapters.browser_automation import ConnectFn, LaunchFn


@pytest.fixture(autouse=True)
def _redirect_real_temp_dirs_into_tmp_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Every `open_page()` call creates one real `tempfile.mkdtemp()` directory, even with a

    faked launch (the temp dir is created before `launch` is ever called). Redirecting it into
    pytest's own auto-cleaned `tmp_path` here, once, keeps every real test in this file hermetic
    without needing each one to remember its own cleanup -- real `close()` calls are still
    exercised directly, where a test's own point is proving `close()` itself works.
    """
    real_mkdtemp = tempfile.mkdtemp

    def mkdtemp(*, prefix: str) -> str:
        return real_mkdtemp(prefix=prefix, dir=tmp_path)

    monkeypatch.setattr("jarvis.adapters.browser_automation.tempfile.mkdtemp", mkdtemp)


_HAS_BRAVE_BROWSER = shutil.which("brave-browser") is not None
_FIXTURE_PAGE = (
    Path(__file__).parent.parent.parent / "fixtures" / "browser_automation_page.html"
).resolve()
_FAKE_DEBUG_PORT = 9222
_FAKE_PROCESS_PID = 4242
_MIN_REAL_PNG_BYTE_LENGTH = 100


class _FakeProcess:
    """A minimal, real fake standing in for subprocess.Popen's own real shape."""

    def __init__(self, pid: int = 4242) -> None:
        self.pid = pid
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True


class _FakeCdpSocket:
    """A minimal, real fake CDP socket: one pre-programmed raw response, sent verbatim."""

    def __init__(self, response: dict[str, object]) -> None:
        self._response = response
        self.closed = False
        self.sent: list[dict[str, object]] = []

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def recv(self) -> str:
        return json.dumps(self._response)

    async def close(self) -> None:
        self.closed = True


def _result_response(result: dict[str, object]) -> dict[str, object]:
    return {"id": 1, "result": result}


def _error_response(message: str) -> dict[str, object]:
    return {"id": 1, "error": {"message": message}}


def _fake_connect_sequence(
    responses: Sequence[dict[str, object]],
) -> tuple[ConnectFn, list[str], list[_FakeCdpSocket]]:
    """Return (connect_fn, uris, sockets) -- one fake socket per call, in order."""
    remaining = list(responses)
    uris: list[str] = []
    sockets: list[_FakeCdpSocket] = []

    async def connect(uri: str) -> _FakeCdpSocket:
        uris.append(uri)
        socket = _FakeCdpSocket(remaining.pop(0))
        sockets.append(socket)
        return socket

    return connect, uris, sockets


def _launch_that_writes_devtools_port(
    port: int, browser_ws_path: str, process: _FakeProcess | None = None
) -> LaunchFn:
    """Return a fake launch fn that writes a real DevToolsActivePort file, mirroring Chromium."""
    real_process = process or _FakeProcess()

    def launch(argv: tuple[str, ...]) -> _FakeProcess:
        user_data_dir = next(
            Path(arg.removeprefix("--user-data-dir="))
            for arg in argv
            if arg.startswith("--user-data-dir=")
        )
        (user_data_dir / "DevToolsActivePort").write_text(
            f"{port}\n{browser_ws_path}\n", encoding="utf-8"
        )
        return real_process

    return launch


async def test_wait_for_devtools_active_port_parses_a_real_file(tmp_path: Path) -> None:
    (tmp_path / "DevToolsActivePort").write_text(
        "9222\n/devtools/browser/real-uuid\n", encoding="utf-8"
    )

    port, path = await _wait_for_devtools_active_port(tmp_path, timeout=1.0)

    assert port == _FAKE_DEBUG_PORT
    assert path == "/devtools/browser/real-uuid"


async def test_wait_for_devtools_active_port_raises_after_a_real_timeout(tmp_path: Path) -> None:
    with pytest.raises(BrowserLaunchFailedError, match="never became reachable"):
        await _wait_for_devtools_active_port(tmp_path, timeout=0.05)


async def test_open_page_returns_a_real_handle_wired_through_launch_and_connect() -> None:
    connect, uris, _ = _fake_connect_sequence(
        [
            _result_response({"targetId": "target-abc"}),
            _result_response({"result": {"value": "complete"}}),
        ]
    )
    launch = _launch_that_writes_devtools_port(9222, "/devtools/browser/real-uuid")
    adapter = CdpBrowserAutomationAdapter(launch=launch, connect=connect)

    handle = await adapter.open_page("https://example.invalid")

    assert handle.debug_port == _FAKE_DEBUG_PORT
    assert handle.target_id == "target-abc"
    assert handle.process_id == _FAKE_PROCESS_PID
    assert Path(handle.user_data_dir).is_dir()
    assert uris[0] == "ws://127.0.0.1:9222/devtools/browser/real-uuid"
    assert uris[1] == "ws://127.0.0.1:9222/devtools/page/target-abc"


async def test_open_page_sends_the_real_url_via_target_create_target() -> None:
    connect, _, sockets = _fake_connect_sequence(
        [
            _result_response({"targetId": "target-abc"}),
            _result_response({"result": {"value": "complete"}}),
        ]
    )
    launch = _launch_that_writes_devtools_port(9222, "/devtools/browser/real-uuid")
    adapter = CdpBrowserAutomationAdapter(launch=launch, connect=connect)

    await adapter.open_page("https://example.invalid/path")

    assert sockets[0].sent == [
        {
            "id": 1,
            "method": "Target.createTarget",
            "params": {"url": "https://example.invalid/path"},
        }
    ]


async def test_open_page_polls_readiness_until_complete() -> None:
    connect, _, _sockets = _fake_connect_sequence(
        [
            _result_response({"targetId": "target-abc"}),
            _result_response({"result": {"value": "loading"}}),
            _result_response({"result": {"value": "complete"}}),
        ]
    )
    launch = _launch_that_writes_devtools_port(9222, "/devtools/browser/real-uuid")
    adapter = CdpBrowserAutomationAdapter(launch=launch, connect=connect)

    handle = await adapter.open_page("https://example.invalid")

    assert handle.target_id == "target-abc"


async def test_open_page_raises_when_launch_itself_fails() -> None:
    def launch(argv: tuple[str, ...]) -> _FakeProcess:  # noqa: ARG001
        raise OSError("brave-browser: command not found")

    adapter = CdpBrowserAutomationAdapter(launch=launch)

    with pytest.raises(BrowserLaunchFailedError, match="Failed to launch"):
        await adapter.open_page("https://example.invalid")


async def test_open_page_terminates_the_process_when_devtools_port_never_appears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("jarvis.adapters.browser_automation._DEVTOOLS_PORT_TIMEOUT", 0.05)
    monkeypatch.setattr("jarvis.adapters.browser_automation._POLL_INTERVAL", 0.01)
    process = _FakeProcess()

    def launch(argv: tuple[str, ...]) -> _FakeProcess:  # noqa: ARG001
        return process  # never writes DevToolsActivePort

    adapter = CdpBrowserAutomationAdapter(launch=launch)

    with pytest.raises(BrowserLaunchFailedError, match="never became reachable"):
        await adapter.open_page("https://example.invalid")
    assert process.terminated is True


async def test_open_page_raises_when_create_target_returns_no_target_id() -> None:
    connect, _, _sockets = _fake_connect_sequence([_result_response({})])
    launch = _launch_that_writes_devtools_port(9222, "/devtools/browser/real-uuid")
    adapter = CdpBrowserAutomationAdapter(launch=launch, connect=connect)

    with pytest.raises(BrowserLaunchFailedError, match="no real targetId"):
        await adapter.open_page("https://example.invalid")


async def test_open_page_raises_and_terminates_on_a_real_cdp_error() -> None:
    connect, _, _sockets = _fake_connect_sequence([_error_response("target creation failed")])
    process = _FakeProcess()
    launch = _launch_that_writes_devtools_port(9222, "/devtools/browser/real-uuid", process)
    adapter = CdpBrowserAutomationAdapter(launch=launch, connect=connect)

    with pytest.raises(BrowserLaunchFailedError, match="target creation failed"):
        await adapter.open_page("https://example.invalid")
    assert process.terminated is True


async def test_capture_screenshot_returns_real_decoded_png_bytes() -> None:
    real_png_bytes = b"\x89PNG\r\n\x1a\nfake-but-real-bytes"
    encoded = base64.b64encode(real_png_bytes).decode("ascii")
    connect, uris, _ = _fake_connect_sequence([_result_response({"data": encoded})])
    adapter = CdpBrowserAutomationAdapter(connect=connect)
    handle = PageHandle(
        debug_port=9222, target_id="target-abc", process_id=1, user_data_dir="/tmp/fake-profile"
    )

    screenshot = await adapter.capture_screenshot(handle)

    assert screenshot == real_png_bytes
    assert uris == ["ws://127.0.0.1:9222/devtools/page/target-abc"]


async def test_capture_screenshot_raises_when_no_real_data_is_returned() -> None:
    connect, _, _sockets = _fake_connect_sequence([_result_response({})])
    adapter = CdpBrowserAutomationAdapter(connect=connect)
    handle = PageHandle(
        debug_port=9222, target_id="target-abc", process_id=1, user_data_dir="/tmp/fake-profile"
    )

    with pytest.raises(BrowserActionFailedError, match="no real image data"):
        await adapter.capture_screenshot(handle)


async def test_query_dom_returns_the_real_matched_outer_html() -> None:
    connect, uris, _ = _fake_connect_sequence(
        [_result_response({"result": {"value": '<div id="marker">hi</div>'}})]
    )
    adapter = CdpBrowserAutomationAdapter(connect=connect)
    handle = PageHandle(
        debug_port=9222, target_id="target-abc", process_id=1, user_data_dir="/tmp/fake-profile"
    )

    html = await adapter.query_dom(handle, "#marker")

    assert html == '<div id="marker">hi</div>'
    assert uris == ["ws://127.0.0.1:9222/devtools/page/target-abc"]


async def test_query_dom_returns_none_when_nothing_matches() -> None:
    connect, _, _sockets = _fake_connect_sequence([_result_response({"result": {"value": None}})])
    adapter = CdpBrowserAutomationAdapter(connect=connect)
    handle = PageHandle(
        debug_port=9222, target_id="target-abc", process_id=1, user_data_dir="/tmp/fake-profile"
    )

    html = await adapter.query_dom(handle, "#does-not-exist")

    assert html is None


async def test_close_kills_a_real_running_process() -> None:
    """A real, harmless `sleep` subprocess -- proves close() really terminates a real pid."""
    process = subprocess.Popen(["sleep", "30"])
    adapter = CdpBrowserAutomationAdapter()
    handle = PageHandle(
        debug_port=9222,
        target_id="target-abc",
        process_id=process.pid,
        user_data_dir="/tmp/fake-profile",
    )

    await adapter.close(handle)
    process.wait(timeout=5)

    assert process.returncode is not None


async def test_close_is_a_noop_for_an_already_gone_process() -> None:
    adapter = CdpBrowserAutomationAdapter()
    process = subprocess.Popen(["true"])
    process.wait(timeout=5)

    handle = PageHandle(
        debug_port=9222,
        target_id="target-abc",
        process_id=process.pid,
        user_data_dir="/tmp/fake-profile",
    )
    await adapter.close(handle)  # must not raise, even though the process is already gone


@pytest.mark.skipif(
    not _HAS_BRAVE_BROWSER,
    reason=(
        "Requires a real, installed brave-browser binary -- not present on headless CI "
        "runners (confirmed: .github/workflows/ci.yml never installs it). Live-verified "
        "on the real development machine during WP-68; see this work package's own "
        "commit message for the real, live result."
    ),
)
async def test_real_cdp_flow_against_a_local_page() -> None:
    """The real, live proof: open a real page, capture a real screenshot, query the real DOM."""
    adapter = CdpBrowserAutomationAdapter()
    handle = await adapter.open_page(_FIXTURE_PAGE.as_uri())
    try:
        screenshot = await adapter.capture_screenshot(handle)
        html = await adapter.query_dom(handle, "#marker")
    finally:
        await adapter.close(handle)

    assert screenshot.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(screenshot) > _MIN_REAL_PNG_BYTE_LENGTH
    assert html == '<div id="marker">jarvis-cdp-live-check</div>'
