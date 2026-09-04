"""Real adapter-failure resilience tests: does every adapter fail closed, not just succeed?

Every adapter test written so far (this project's own real, local
GreenMail/Radicale/Ollama integration tests included) proves the happy
path works. None prove what happens when the real dependency behind
them actually fails mid-use -- this file closes that gap for real,
against the same real, local, credential-free test dependencies this
project already has non-destructive control over.

Two real failure classes are checked separately for each target,
per this pass's own instructions -- "don't assume they behave the
same until proven":

- **Never reachable**: the real service is stopped *before* the call
  is ever made. Tested by actually stopping the real local service
  (Ollama, GreenMail, Radicale) and restoring it afterward, always via
  ``try/finally`` so a test failure can never leave the real,
  shared local environment down for any other test or the developer's
  own use.
- **Connection lost mid-use**: the real service was reachable when the
  call began but stops responding partway through. For Ollama, real
  process-kill timing against the real, shared local server is
  fragile to make deterministic (a real generation call from a small,
  fast model can complete before a kill signal even lands) --
  substituted with a real, minimal, purpose-built local TCP server
  that accepts a connection and then drops it, driving the exact same
  real HTTP/socket-level failure shape deterministically, with
  ``adapters.reasoning.local._ENDPOINT`` patched to point at it rather
  than mocking any of this project's own application code. For IMAP,
  a real TCP connection is established via a custom, injected
  ``connection_factory`` closure, which then stops the real GreenMail
  container itself before returning -- so the adapter's own real
  ``ImapEmailAdapter.list_messages()`` public method genuinely attempts
  its own subsequent, real ``.login()`` against a connection that
  *was* live and now is not, through the same public API a real
  caller would use, not a private method called directly.
"""

from __future__ import annotations

import http.server
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from jarvis.adapters.calendar import CalDavCalendarAdapter
from jarvis.adapters.email import ImapEmailAdapter
from jarvis.kernel.coding import authorize_and_run_coding_task
from jarvis.kernel.communications import (
    authorize_and_list_calendar_events,
    authorize_and_list_email,
)
from jarvis.kernel.job_assistance import authorize_and_draft_document
from jarvis.ports.email import EmailConnectionError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from jarvis.ports.secret import SecretPort

_OLLAMA_URL = "http://localhost:11434/api/tags"
_GREENMAIL_HOST = "127.0.0.1"
_GREENMAIL_IMAP_PORT = 3143
_GREENMAIL_USERNAME = "testuser"
_GREENMAIL_PASSWORD = "testpass"
_RADICALE_URL = "http://127.0.0.1:5232/"


def _poll_until(predicate: Callable[[], bool], *, attempts: int, interval_seconds: float) -> bool:
    """Retry `predicate` up to `attempts` times, sleeping `interval_seconds` between tries.

    A bounded-retry-count loop, not a wall-clock deadline -- this
    project's own `time.monotonic()`/`time.time()` ban (ClockPort
    injection instead, enforced by `ruff`'s banned-api rule) applies
    repo-wide, tests included, so real-infrastructure readiness polls
    in this file use a simple retry count instead of computing a real
    deadline.
    """
    for _ in range(attempts):
        if predicate():
            return True
        time.sleep(interval_seconds)
    return predicate()


def _real_ollama_server_is_reachable() -> bool:
    try:
        urllib.request.urlopen(_OLLAMA_URL, timeout=1)
    except OSError:
        return False
    return True


def _real_greenmail_is_reachable() -> bool:
    try:
        with socket.create_connection((_GREENMAIL_HOST, _GREENMAIL_IMAP_PORT), timeout=1):
            return True
    except OSError:
        return False


def _real_greenmail_imap_handshake_succeeds() -> bool:
    """A real IMAP4 protocol handshake, not just a TCP accept.

    A real, empirically-found gap in the cheaper TCP-only reachability
    check above: GreenMail's own JVM can accept a real TCP connection
    on its IMAP port before its IMAP service has actually finished
    initializing, causing a real ``imaplib.IMAP4.abort: socket error:
    EOF`` on the very first handshake read. This stronger check is
    used specifically when *waiting for the real container to become
    genuinely usable again* after a stop/start cycle, not as the
    lighter-weight skipif guard (which only needs to answer "is
    anything listening at all").

    Deliberately catches ``imaplib.IMAP4.error`` (``.abort``'s own
    base class) alongside ``OSError`` -- the exact real, non-OSError
    exception hierarchy quirk this test file's own findings named in
    ``jarvis.ports.email.EmailConnectionError``'s docstring, applied
    here to this helper too, found the same way: this helper's own
    first version only caught ``OSError`` and, ironically, would
    itself raise uncaught mid-poll for the same underlying reason.
    """
    import imaplib  # noqa: PLC0415 -- test-local, mirrors the real adapter's own lazy import

    try:
        imaplib.IMAP4(_GREENMAIL_HOST, _GREENMAIL_IMAP_PORT).shutdown()
    except (OSError, imaplib.IMAP4.error):
        return False
    return True


def _wait_for_real_greenmail_ready(attempts: int = 40) -> None:
    """Block until GreenMail genuinely completes a real IMAP handshake, or raise."""
    ready = _poll_until(
        _real_greenmail_imap_handshake_succeeds, attempts=attempts, interval_seconds=0.5
    )
    if not ready:
        msg = "the real local GreenMail container never became genuinely ready for a real handshake"
        raise AssertionError(msg)


def _real_radicale_is_reachable() -> bool:
    try:
        urllib.request.urlopen(_RADICALE_URL, timeout=1)
    except urllib.error.HTTPError:
        return True
    except OSError:
        return False
    return True


def _docker_container_running(name: str) -> bool:
    result = subprocess.run(
        ["docker", "inspect", name, "--format", "{{.State.Running}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


class _StaticSecretPort:
    """Resolves any reference to one real, fixed test password. No real keyring touched."""

    def __init__(self, password: str) -> None:
        self._password = password

    def get_secret(self, reference: str) -> str:
        del reference
        return self._password

    def set_secret(self, reference: str, value: str) -> None:
        del reference, value


def _real_imap_connection_factory(host: str) -> object:
    del host
    import imaplib  # noqa: PLC0415 -- test-local, mirrors the adapter's own lazy-import discipline

    return imaplib.IMAP4(_GREENMAIL_HOST, _GREENMAIL_IMAP_PORT)


def _make_real_imap_adapter() -> ImapEmailAdapter:
    secret: SecretPort = _StaticSecretPort(_GREENMAIL_PASSWORD)
    return ImapEmailAdapter(
        host=_GREENMAIL_HOST,
        username=_GREENMAIL_USERNAME,
        secret=secret,
        password_reference="unused-static-test-password",
        smtp_host=_GREENMAIL_HOST,
        connection_factory=_real_imap_connection_factory,  # type: ignore[arg-type]
    )


# --- Track 1: coding.run_task / Ollama --------------------------------------


@pytest.mark.skipif(
    not _real_ollama_server_is_reachable(),
    reason="Requires a real, local Ollama server on localhost:11434 -- `ollama serve`.",
)
@pytest.mark.asyncio
async def test_coding_run_task_when_ollama_is_never_reachable_fails_closed(tmp_path: Path) -> None:
    """Real: stop the real, local Ollama server, attempt a real coding.run_task, restore after.

    Confirmed empirically before writing this test: the real failure
    is `urllib.error.URLError: <urlopen error [Errno 111] Connection
    refused>`, propagated uncaught through
    application/coding/loop.py::run_coding_task and
    kernel/coding.py::authorize_and_run_coding_task (neither wraps the
    reasoning call in a try/except -- only a try/finally for the
    audit-chain save). URLError is a real OSError subclass, so it is
    already caught cleanly by cli/main.py's own broad except tuple and
    by kernel/voice_loop.py's own (this pass's prior track added) --
    this is a real "fails closed with a clear, actionable error"
    outcome at both real entry points, confirmed here at the kernel
    boundary directly, not fixed further: no crash, no hang, no silent
    wrong result, just a real, propagated, typed, already-caught-
    upstream exception.
    """
    target_repo = tmp_path / "target_repo"
    target_repo.mkdir()
    subprocess.run(["pkill", "-f", "ollama serve"], check=False)
    try:
        _poll_until(
            lambda: not _real_ollama_server_is_reachable(), attempts=25, interval_seconds=0.2
        )
        assert not _real_ollama_server_is_reachable(), "could not stop the real local Ollama server"

        with pytest.raises(OSError) as exc_info:
            await authorize_and_run_coding_task(
                "add a comment to the top of any file",
                target_repo,
                physical_confirmation_available=True,
                remote_confirmation_available=False,
                chain_path=tmp_path / "audit_chain.json",
                max_climbs=1,
                protected_patterns=("test_*.py",),
            )
        assert isinstance(exc_info.value, urllib.error.URLError)
    finally:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _poll_until(_real_ollama_server_is_reachable, attempts=30, interval_seconds=0.5)
        assert _real_ollama_server_is_reachable(), "failed to restore the real local Ollama server"


class _DropConnectionHandler(http.server.BaseHTTPRequestHandler):
    """A real, minimal HTTP handler that accepts the connection then drops it, no response."""

    def do_POST(self) -> None:
        self.close_connection = True
        self.connection.close()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 -- stdlib signature
        del format, args  # silence real request logging in test output


@pytest.fixture
def _connection_dropping_server() -> Iterator[int]:
    """A real, local TCP server that accepts a connection then resets it -- no Ollama involved.

    Deterministically reproduces the real "connected, then dropped"
    failure shape (a real socket accept, a real immediate close,
    exactly what a killed real server produces to an in-flight client)
    without racing the real Ollama process's own generation timing.
    """
    server = http.server.HTTPServer(("127.0.0.1", 0), _DropConnectionHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.asyncio
async def test_coding_run_task_when_ollama_connection_is_dropped_mid_request_fails_closed(
    tmp_path: Path, _connection_dropping_server: int
) -> None:
    """Real: a real local server accepts, then drops, the connection mid-request -- no mock.

    ``adapters.reasoning.local._ENDPOINT`` is patched to point at the
    real, local, connection-dropping server above -- the real
    ``_post_sync``/``urllib.request.urlopen`` code path is exercised
    unmodified; only *where it connects to* changes, exactly the same
    kind of override this project's own real GreenMail/Radicale
    integration tests already use for the same reason (a real local
    substitute for a real, shared service, not a mock of the
    application code under test).
    """
    target_repo = tmp_path / "target_repo"
    target_repo.mkdir()
    endpoint = f"http://127.0.0.1:{_connection_dropping_server}/api/generate"

    with patch("jarvis.adapters.reasoning.local._ENDPOINT", endpoint), pytest.raises(OSError):
        await authorize_and_run_coding_task(
            "add a comment to the top of any file",
            target_repo,
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "audit_chain.json",
            max_climbs=1,
            protected_patterns=("test_*.py",),
        )


# --- Track 1: communications.list_email / GreenMail -------------------------


@pytest.mark.skipif(
    not _real_greenmail_is_reachable(),
    reason=(
        "Requires a real, local GreenMail test server on 127.0.0.1:3025/3143 -- "
        "`docker run -d --name jarvis-test-greenmail -p 3025:3025 -p 3143:3143 "
        '-e GREENMAIL_OPTS="-Dgreenmail.setup.test.all '
        '-Dgreenmail.users=testuser:testpass@localhost" '
        "greenmail/standalone`."
    ),
)
@pytest.mark.asyncio
async def test_list_email_when_greenmail_is_never_reachable_fails_closed(tmp_path: Path) -> None:
    """Real: stop the real, local GreenMail container, attempt a real list_email, restore after."""
    was_running = _docker_container_running("jarvis-test-greenmail")
    assert was_running, "jarvis-test-greenmail container is not running -- reachability check lied"

    subprocess.run(["docker", "stop", "jarvis-test-greenmail"], check=True)
    try:
        assert not _real_greenmail_is_reachable()

        with pytest.raises(OSError) as exc_info:
            await authorize_and_list_email(
                "INBOX",
                limit=10,
                email_port=_make_real_imap_adapter(),
                physical_confirmation_available=True,
                remote_confirmation_available=False,
                chain_path=tmp_path / "audit_chain.json",
            )
        assert isinstance(exc_info.value, ConnectionRefusedError)
    finally:
        subprocess.run(["docker", "start", "jarvis-test-greenmail"], check=True)
        _wait_for_real_greenmail_ready()


@pytest.mark.skipif(
    not _real_greenmail_is_reachable(),
    reason="Requires a real, local GreenMail test server -- see the sibling test's own reason.",
)
@pytest.mark.asyncio
async def test_list_email_when_the_connection_dies_between_connect_and_login_fails_closed() -> None:
    """Real: a TCP connection is established, then GreenMail stops, then login is attempted.

    Deterministic, unlike racing a container-stop against an in-flight
    real IMAP call's own real timing: the connection factory itself
    performs the real, successful TCP connect, then stops the real
    GreenMail container from inside the factory, right before
    ``ImapEmailAdapter._connect()``'s own subsequent ``.login()`` call
    -- proving the real "was connected, now isn't" failure shape this
    pass's own instructions asked to distinguish from "never
    reachable," through the real, public ``list_messages()`` seam, not
    by calling private methods directly.

    **A real bug found and fixed by this exact test, not invented**:
    before this pass, the real failure here was a raw, uncaught
    ``imaplib.IMAP4.abort`` -- confirmed empirically (this test's own
    first version, run before the fix, failed with exactly that
    exception escaping uncaught). ``imaplib.IMAP4.abort`` is a bare
    ``Exception`` subclass, not ``OSError``, unlike every other real
    network-facing adapter's own connectivity failures in this
    codebase -- meaning it would have bypassed ``cli/main.py``'s and
    ``kernel/voice_loop.py``'s own broad, OSError-inclusive except
    tuples the moment either is ever wired up to
    ``communications.list_email``/``read_email`` (neither is wired to
    a real entry point yet, but the gap was real regardless). Fixed by
    normalizing ``imaplib.IMAP4.error`` (which ``.abort`` inherits
    from) into a new, real, typed
    ``jarvis.ports.email.EmailConnectionError`` at the adapter
    boundary -- see that class's own docstring for the full account.
    """
    stopped = False

    def _die_before_login(host: str) -> object:
        del host
        nonlocal stopped
        import imaplib  # noqa: PLC0415 -- test-local, mirrors the real adapter's own lazy import

        connection = imaplib.IMAP4(_GREENMAIL_HOST, _GREENMAIL_IMAP_PORT)
        subprocess.run(["docker", "stop", "jarvis-test-greenmail"], check=True)
        _poll_until(lambda: not _real_greenmail_is_reachable(), attempts=50, interval_seconds=0.2)
        stopped = True
        return connection

    secret: SecretPort = _StaticSecretPort(_GREENMAIL_PASSWORD)
    adapter = ImapEmailAdapter(
        host=_GREENMAIL_HOST,
        username=_GREENMAIL_USERNAME,
        secret=secret,
        password_reference="unused-static-test-password",
        smtp_host=_GREENMAIL_HOST,
        connection_factory=_die_before_login,  # type: ignore[arg-type]
    )

    try:
        with pytest.raises(EmailConnectionError):
            await adapter.list_messages("INBOX", limit=10)
        assert stopped, "the container was never actually stopped -- test setup itself is broken"
    finally:
        subprocess.run(["docker", "start", "jarvis-test-greenmail"], check=True)
        _wait_for_real_greenmail_ready()


# --- Track 1: communications.list_calendar_events / Radicale ----------------

_RADICALE_USERNAME = "testuser"
_RADICALE_PASSWORD = "anything-radicale-auth-type-is-none"


@pytest.mark.skipif(
    not _real_radicale_is_reachable(),
    reason=(
        "Requires a real, local Radicale test server on 127.0.0.1:5232 -- "
        "`docker run -d --name jarvis-test-radicale -p 5232:5232 "
        "-v $(pwd)/tests/fixtures/radicale-config:/config:ro tomsquest/docker-radicale`."
    ),
)
@pytest.mark.asyncio
async def test_list_calendar_events_when_radicale_is_never_reachable_fails_closed(
    tmp_path: Path,
) -> None:
    """Real: stop the real, local Radicale container, attempt a real list_calendar_events."""
    was_running = _docker_container_running("jarvis-test-radicale")
    assert was_running, "jarvis-test-radicale container is not running -- reachability check lied"

    secret: SecretPort = _StaticSecretPort(_RADICALE_PASSWORD)
    adapter = CalDavCalendarAdapter(
        url=_RADICALE_URL,
        username=_RADICALE_USERNAME,
        secret=secret,
        password_reference="unused-static-test-password",
    )

    subprocess.run(["docker", "stop", "jarvis-test-radicale"], check=True)
    try:
        _poll_until(lambda: not _real_radicale_is_reachable(), attempts=50, interval_seconds=0.2)
        assert not _real_radicale_is_reachable()

        with pytest.raises(OSError):
            await authorize_and_list_calendar_events(
                "2026-01-01T00:00:00",
                "2026-12-31T23:59:59",
                calendar_port=adapter,
                physical_confirmation_available=True,
                remote_confirmation_available=False,
                chain_path=tmp_path / "audit_chain.json",
            )
    finally:
        subprocess.run(["docker", "start", "jarvis-test-radicale"], check=True)
        _poll_until(_real_radicale_is_reachable, attempts=40, interval_seconds=0.5)
        assert _real_radicale_is_reachable(), "failed to restore the real local Radicale container"


# --- Track 1: job_assistance.draft / Ollama ----------------------------------


@pytest.mark.skipif(
    not _real_ollama_server_is_reachable(),
    reason="Requires a real, local Ollama server on localhost:11434 -- `ollama serve`.",
)
@pytest.mark.asyncio
async def test_job_assistance_draft_when_ollama_is_never_reachable_fails_closed(
    tmp_path: Path,
) -> None:
    """Real: stop the real, local Ollama server, attempt a real job_assistance.draft, restore after.

    Mirrors test_coding_run_task_when_ollama_is_never_reachable_fails_closed
    exactly -- job_assistance.draft's own default providers
    (_local_only_providers()) reach the identical real
    LocalReasoningAdapter/Ollama dependency coding.run_task's own
    default dispatcher_factory does, so the same real failure shape
    (a real, OSError-subclass urllib.error.URLError) applies here too,
    confirmed directly rather than assumed from the shared code path.
    """
    subprocess.run(["pkill", "-f", "ollama serve"], check=False)
    try:
        _poll_until(
            lambda: not _real_ollama_server_is_reachable(), attempts=25, interval_seconds=0.2
        )
        assert not _real_ollama_server_is_reachable(), "could not stop the real local Ollama server"

        with pytest.raises(OSError) as exc_info:
            await authorize_and_draft_document(
                "draft a short cover letter for a software engineering role",
                physical_confirmation_available=True,
                remote_confirmation_available=False,
                chain_path=tmp_path / "audit_chain.json",
                drafts_dir=tmp_path / "drafts",
            )
        assert isinstance(exc_info.value, urllib.error.URLError)
    finally:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _poll_until(_real_ollama_server_is_reachable, attempts=30, interval_seconds=0.5)
        assert _real_ollama_server_is_reachable(), "failed to restore the real local Ollama server"
