"""Real IMAP/CalDAV integration tests against real, local, credential-free test servers.

Closes the actual gap named repeatedly in past reports: "the
live-credential-gated integration test remains unmet, no real
test-account credentials configured." The fix is not real credentials
-- it is a real, local, open-source test server, requiring none.

Two real servers, launched via Docker -- manually, on a developer's
own machine (the exact real commands are in each real skipif's own
``reason=`` message below), or automatically in CI, via
``.github/workflows/ci.yml``'s own service-container config:

- **GreenMail** (``greenmail/standalone``) -- a real, open-source
  Java IMAP/SMTP test server, purpose-built for exactly this ("start
  a real mailbox server for integration tests"), not a general-purpose
  mail server repurposed. Plain (non-SSL) IMAP on port 3143, plain SMTP
  on port 3025 -- matching ``ImapEmailAdapter``'s own real
  ``connection_factory``/``smtp_connection_factory`` override seam,
  which takes only a host string, no port; both are supplied here as
  closures binding the real local port instead.
- **Radicale** (``tomsquest/docker-radicale``) -- a real, open-source,
  lightweight CalDAV server. ``auth.type = none`` (see
  ``tests/fixtures/radicale-config/config``) -- any username/password
  is accepted; this is a real, throwaway, local-only test fixture, not
  a real account, matching the same "credential-free" requirement
  GreenMail's own default test user meets.

Every test below is real, not mocked -- real TCP connections to
``127.0.0.1``, real IMAP/SMTP/CalDAV protocol exchanges, real server-
side state. Gated by a real reachability probe (TCP/HTTP connect,
short timeout, wrapped in ``try/except OSError``), the same pattern
``adapters/reasoning/local.py``'s own
``_real_ollama_server_is_reachable`` already established -- honestly
skipped when the local server isn't running (a developer's own
machine with nothing started), never a hard failure, and genuinely
exercised in CI, where the service containers are always up.

**Read-path only for email** (``list_messages``/``read_message``),
matching this project's own already-stated scope discipline for this
exact test (the retired placeholder's own docstring, matching
``m6a-communications.md``'s acceptance criterion 6, named "read-path
only"). A real test message is seeded into the mailbox via a raw,
direct ``smtplib.SMTP`` call in this module's own fixture -- not
through ``ImapEmailAdapter.send_message`` itself, keeping this test's
own use of the adapter strictly read-only, the seed mechanism
completely separate. Calendar gets both real reads and one real,
attendee-less event creation -- attendee-less `create_event` was never
gated by ADR-0057/ADR-0059 in the first place (both floor
`Tier.CONFIRM`, not `MANUAL_ONLY`, regardless of this test's own
provenance), so exercising it here for real is safe and in scope.
"""

from __future__ import annotations

import smtplib
import socket
import sys
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage as StdlibEmailMessage
from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.calendar import CalDavCalendarAdapter
from jarvis.adapters.email import ImapEmailAdapter
from jarvis.cli.main import main
from jarvis.domain.calendar import CalendarEventDraft
from jarvis.ports.email import EmailMessageNotFoundError

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.email import EmailMessage, EmailSummary
    from jarvis.ports.secret import SecretPort

_GREENMAIL_HOST = "127.0.0.1"
_GREENMAIL_IMAP_PORT = 3143
_GREENMAIL_SMTP_PORT = 3025
_GREENMAIL_USERNAME = "testuser"
_GREENMAIL_PASSWORD = "testpass"

_RADICALE_URL = "http://127.0.0.1:5232/"
_RADICALE_USERNAME = "testuser"
_RADICALE_PASSWORD = "anything-radicale-auth-type-is-none"


def _real_greenmail_is_reachable() -> bool:
    """A real, short-timeout TCP probe against GreenMail's own real IMAP port.

    Mirrors ``adapters/reasoning/local.py``'s own
    ``_real_ollama_server_is_reachable`` -- honestly skip, never a hard
    failure, when no local test server is running.
    """
    try:
        with socket.create_connection((_GREENMAIL_HOST, _GREENMAIL_IMAP_PORT), timeout=1):
            return True
    except OSError:
        return False


def _real_radicale_is_reachable() -> bool:
    """A real, short-timeout HTTP probe against Radicale's own real root."""
    try:
        urllib.request.urlopen(_RADICALE_URL, timeout=1)
    except urllib.error.HTTPError:
        return True  # A real HTTP response (even 401/404) means the real server is up.
    except OSError:
        return False
    return True


class _StaticSecretPort:
    """Resolves any reference to one real, fixed test password. No real keyring touched."""

    def __init__(self, password: str) -> None:
        self._password = password

    def get_secret(self, reference: str) -> str:
        del reference
        return self._password

    def set_secret(self, reference: str, value: str) -> None:
        del reference, value


def _seed_real_message_via_raw_smtp(message_id: str, subject: str, body: str) -> None:
    """Deliver one real message into the real GreenMail mailbox via raw stdlib smtplib.

    Deliberately not through ``ImapEmailAdapter.send_message`` -- this
    module's own tests exercise the adapter's read path only; seeding
    is real test infrastructure, kept entirely separate from what's
    under test.
    """
    message = StdlibEmailMessage()
    message["Message-ID"] = message_id
    message["From"] = f"{_GREENMAIL_USERNAME}@localhost"
    message["To"] = f"{_GREENMAIL_USERNAME}@localhost"
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(_GREENMAIL_HOST, _GREENMAIL_SMTP_PORT, timeout=10) as smtp:
        smtp.send_message(message)


def _real_imap_connection_factory(host: str) -> object:
    """Ignore ``host`` (production hostname), dial the real local GreenMail port instead."""
    del host
    import imaplib  # noqa: PLC0415 -- test-local, mirrors the adapter's own lazy-import discipline

    return imaplib.IMAP4(_GREENMAIL_HOST, _GREENMAIL_IMAP_PORT)


def _real_smtp_connection_factory(host: str) -> object:
    """Ignore ``host``, dial the real local GreenMail SMTP port instead."""
    del host
    return smtplib.SMTP(_GREENMAIL_HOST, _GREENMAIL_SMTP_PORT)


def _make_real_imap_adapter() -> ImapEmailAdapter:
    secret: SecretPort = _StaticSecretPort(_GREENMAIL_PASSWORD)
    return ImapEmailAdapter(
        host=_GREENMAIL_HOST,
        username=_GREENMAIL_USERNAME,
        secret=secret,
        password_reference="unused-static-test-password",
        smtp_host=_GREENMAIL_HOST,
        connection_factory=_real_imap_connection_factory,  # type: ignore[arg-type]
        smtp_connection_factory=_real_smtp_connection_factory,  # type: ignore[arg-type]
    )


def _ensure_real_radicale_calendar_exists() -> None:
    """Create the real test calendar collection if Radicale doesn't already have one.

    ``CalDavCalendarAdapter``'s own real ``_real_calendar_factory``
    requires at least one real calendar to already exist for the
    principal (confirmed directly: it raises ``CalendarNotFoundError``
    on an empty list, matching a real, freshly-provisioned CalDAV
    account) -- a real deployment would already have one; this test's
    own fixture provisions it the same way a real setup wizard would,
    kept entirely separate from the adapter under test.
    """
    from caldav.davclient import DAVClient  # noqa: PLC0415 -- test-local, real, heavy import

    client = DAVClient(url=_RADICALE_URL, username=_RADICALE_USERNAME, password=_RADICALE_PASSWORD)
    principal = client.get_principal()
    if not principal.calendars():
        principal.make_calendar(name="Test Calendar")


def _make_real_caldav_adapter() -> CalDavCalendarAdapter:
    secret: SecretPort = _StaticSecretPort(_RADICALE_PASSWORD)
    return CalDavCalendarAdapter(
        url=_RADICALE_URL,
        username=_RADICALE_USERNAME,
        secret=secret,
        password_reference="unused-static-test-password",
    )


_greenmail_skip = pytest.mark.skipif(
    not _real_greenmail_is_reachable(),
    reason=(
        "Requires a real, local GreenMail test server on 127.0.0.1:3025/3143 -- "
        "not running here. Start it with: docker run -d --name jarvis-test-greenmail "
        '-e GREENMAIL_OPTS="-Dgreenmail.setup.test.all '
        "-Dgreenmail.users=testuser:testpass@localhost -Dgreenmail.hostname=0.0.0.0 "
        '-Dgreenmail.auth.disabled" -p 3025:3025 -p 3143:3143 -p 3110:3110 '
        "greenmail/standalone:latest -- or let CI's own service container start it "
        "(.github/workflows/ci.yml). No real mailbox account is required or used."
    ),
)

_radicale_skip = pytest.mark.skipif(
    not _real_radicale_is_reachable(),
    reason=(
        "Requires a real, local Radicale CalDAV test server on 127.0.0.1:5232 -- "
        "not running here. Start it with: docker run -d --name jarvis-test-radicale "
        "-p 5232:5232 -v $(pwd)/tests/fixtures/radicale-config:/config:ro "
        "tomsquest/docker-radicale:latest -- or let CI's own service container start "
        "it (.github/workflows/ci.yml). No real calendar account is required or used."
    ),
)


@_greenmail_skip
async def test_real_list_messages_against_a_local_greenmail_server() -> None:
    """A real ImapEmailAdapter.list_messages() call against the real, local GreenMail server."""
    unique_subject = f"real integration test {uuid.uuid4()}"  # noqa: TID251 -- real test-data uniqueness
    _seed_real_message_via_raw_smtp(
        message_id=f"<{uuid.uuid4()}@localhost>",  # noqa: TID251 -- real test-data uniqueness
        subject=unique_subject,
        body="Real, local, credential-free integration test body.",
    )

    adapter = _make_real_imap_adapter()
    summaries: tuple[EmailSummary, ...] = await adapter.list_messages("INBOX", limit=50)

    assert any(summary.subject == unique_subject for summary in summaries)


@_greenmail_skip
async def test_real_read_message_against_a_local_greenmail_server() -> None:
    """A real ImapEmailAdapter.read_message() call, fetching a real message by its real
    Message-ID, against the real, local GreenMail server."""
    real_message_id = f"<{uuid.uuid4()}@localhost>"  # noqa: TID251 -- real test-data uniqueness, not domain logic
    real_body = f"Real body, unique token: {uuid.uuid4()}"  # noqa: TID251 -- same
    _seed_real_message_via_raw_smtp(
        message_id=real_message_id, subject="read-message test", body=real_body
    )

    adapter = _make_real_imap_adapter()
    message: EmailMessage = await adapter.read_message(real_message_id)

    assert message.message_id == real_message_id
    assert real_body in message.body
    assert message.subject == "read-message test"


@_greenmail_skip
async def test_real_read_message_not_found_raises_against_a_local_greenmail_server() -> None:
    """A real, unrecognized Message-ID against the real server raises the real,
    typed EmailMessageNotFoundError -- not a generic exception, not silently None."""
    adapter = _make_real_imap_adapter()

    with pytest.raises(EmailMessageNotFoundError):
        await adapter.read_message(f"<{uuid.uuid4()}@nonexistent.invalid>")  # noqa: TID251 -- real test-data uniqueness


def _fake_imap_email_adapter_pointed_at_greenmail(
    host: str,
    username: str,
    secret: object,
    password_reference: str,
    *,
    smtp_host: str,
) -> ImapEmailAdapter:
    """Ignore the CLI's own real, production-shaped arguments; return an adapter
    wired to dial the real, local GreenMail server instead.

    ``cli/main.py``'s ``_run_email_subcommand`` always builds
    ``ImapEmailAdapter`` with its own default connection factories
    (real ``IMAP4_SSL``/``SMTP_SSL`` on the standard SSL ports) --
    exactly the same real, pre-existing gap this module's own
    ``_make_real_imap_adapter()`` already works around for the
    kernel-level tests above (GreenMail speaks plain, non-SSL IMAP/SMTP
    on non-standard ports). Patching this one factory function is the
    only way to prove the real CLI *argument-parsing and dispatch*
    path reaches a real server without inventing new CLI flags this
    task's own hard gates forbid (no new ``--imap-port``/``--use-ssl``
    surface, no change to the email adapter's own behavior).
    """
    del host, username, secret, password_reference, smtp_host
    return _make_real_imap_adapter()


@_greenmail_skip
def test_real_cli_email_list_and_read_against_a_local_greenmail_server(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real ``jarvis email list``/``jarvis email read`` CLI path -- not just
    the kernel function directly -- against the real, local GreenMail server."""
    unique_subject = f"real cli integration test {uuid.uuid4()}"  # noqa: TID251 -- real test-data uniqueness
    real_message_id = f"<{uuid.uuid4()}@localhost>"  # noqa: TID251 -- real test-data uniqueness
    real_body = f"Real CLI-path body, unique token: {uuid.uuid4()}"  # noqa: TID251 -- same
    _seed_real_message_via_raw_smtp(
        message_id=real_message_id, subject=unique_subject, body=real_body
    )

    monkeypatch.setattr(
        sys.modules["jarvis.cli.main"],
        "ImapEmailAdapter",
        _fake_imap_email_adapter_pointed_at_greenmail,
    )
    chain_path = tmp_path / "audit_chain.json"
    common_flags = [
        "--imap-host",
        "unused.example.com",
        "--smtp-host",
        "unused.example.com",
        "--username",
        "unused",
        "--password-reference",
        "unused-static-test-password",
        "--physical-confirmation-available",
        "--chain-path",
        str(chain_path),
    ]

    list_exit_code = main(["email", "list", "--limit", "50", *common_flags])
    list_captured = capsys.readouterr()

    assert list_exit_code == 0
    assert "email list: GRANTED" in list_captured.out
    assert unique_subject in list_captured.out

    read_exit_code = main(["email", "read", real_message_id, *common_flags])
    read_captured = capsys.readouterr()

    assert read_exit_code == 0
    assert "email read: GRANTED" in read_captured.out
    assert real_body in read_captured.out
    assert unique_subject in read_captured.out


@_radicale_skip
async def test_real_list_events_against_a_local_radicale_server() -> None:
    """A real CalDavCalendarAdapter.list_events() call against the real, local Radicale server."""
    _ensure_real_radicale_calendar_exists()
    adapter = _make_real_caldav_adapter()
    unique_summary = f"real list-events test {uuid.uuid4()}"  # noqa: TID251 -- real test-data uniqueness
    start = datetime.now(UTC)  # noqa: TID251 -- the test's own independent reference point
    end = start + timedelta(hours=1)

    created_uid = await adapter.create_event(
        CalendarEventDraft(
            summary=unique_summary,
            start=start.isoformat(),
            end=end.isoformat(),
            attendees=(),
        )
    )
    assert created_uid

    events = await adapter.list_events(
        start=(start - timedelta(minutes=5)).isoformat(),
        end=(end + timedelta(minutes=5)).isoformat(),
    )

    assert any(event.summary == unique_summary for event in events)


@_radicale_skip
async def test_real_attendee_less_create_event_against_a_local_radicale_server() -> None:
    """A real, attendee-less CalDavCalendarAdapter.create_event() call -- never gated by
    ADR-0057/ADR-0059 in the first place (both floor Tier.CONFIRM here, not MANUAL_ONLY) --
    proven against a real server, returning a real, non-empty uid."""
    _ensure_real_radicale_calendar_exists()
    adapter = _make_real_caldav_adapter()
    start = datetime.now(UTC)  # noqa: TID251 -- the test's own independent reference point
    end = start + timedelta(hours=1)

    uid = await adapter.create_event(
        CalendarEventDraft(
            summary=f"real attendee-less event {uuid.uuid4()}",  # noqa: TID251 -- real test-data uniqueness
            start=start.isoformat(),
            end=end.isoformat(),
            attendees=(),
        )
    )

    assert isinstance(uid, str)
    assert uid
