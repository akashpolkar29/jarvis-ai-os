"""The CLI's argument parsing and result formatting -- no business logic.

:func:`main` parses argv into a subcommand (``ping``, ``play``,
``pause``, ``next``, ``previous``, ``read``, ``memory``, ``listen``)
and the confirmation/chain-path flags most subcommands share, calls
the matching ``jarvis.kernel`` composition function, and formats the
returned ``Decision`` (and, for ``read``/``memory retrieve``, the
recalled content) for a terminal. It decides nothing about policy or
capabilities itself -- that is exactly the line this ring's own
docstring draws.

``memory`` (M4-gap-closure pass) has its own nested subcommands --
``write``/``retrieve``/``forget``/``pin`` -- each a thin wrapper
around the matching ``jarvis.kernel.memory.authorize_and_*``
function, mirroring this module's own existing ``ping``/``read``
shape (parse, authorize, act only if granted, print the ``Decision``).
**Real, deliberate correction to a claim this module's own history
once made**: an earlier pass's docstring described "no CLI wiring for
memory" as "mirroring M3's own ``docker.*``/``git.*`` precedent" --
that was a misreading. Docker/Git's own kernel functions
(``kernel/desktop.py``) were never wired into this module either, but
not as a template meant to be replicated: nothing in this file's own
history establishes a real "capabilities deliberately get no CLI"
convention to mirror. The actual, only precedent this file has ever
had for "what a CLI wrapper around a capability looks like" is
``ping``/``play``/``pause``/``next``/``previous``/``read`` themselves
-- ``memory``'s subcommands follow that shape instead. **Docker/Git,
and the rest of `kernel/desktop.py`'s real capabilities, were wired
in later** (see the ``open-brave-url``/... paragraph below) -- this
paragraph is kept as the real, historical record of the misreading
that was corrected, not because the gap it describes is still open.

``listen`` (WP-26) is the one subcommand that does not fit that
shape: it runs ``jarvis.kernel.voice_loop.run_voice_loop`` as a
foreground, continuous process rather than authorizing one call and
exiting, and it is the one place in this whole project permitted to
construct a real ``Gtk4PhysicalConfirmationAdapter`` -- ``cli`` sits
above both ``kernel`` and ``adapters`` in the C1 layering and is
unrestricted by C6 ("no GLib in the core"), which is exactly why
``run_voice_loop`` itself takes ``physical_confirmation`` as a
required, undefaulted parameter (see that module's own docstring).
``listen`` does not take the ``--physical-confirmation-available``/
``--remote-confirmation-available`` flags every other subcommand does:
those model a fixed, upfront confirmation state, whereas the voice
loop asks a real, per-utterance question through the GTK4 dialog
instead.

``listen --verbose`` raises ``jarvis``'s own logger hierarchy (every
``logging.getLogger(__name__)`` under the ``jarvis`` package, e.g.
``jarvis.adapters.wake_word``, ``jarvis.kernel.voice_loop``) to DEBUG,
surfacing the diagnostic lines proven useful during live M1
verification (wake-word scores, trigger confirmations, VAD segment
sizes, transcripts, intent resolution results) -- see those modules'
own docstrings. Third-party library loggers (``sounddevice``,
``onnxruntime``, ``openwakeword``, ``faster_whisper``, ``gi``, etc.)
deliberately stay at the root's default level regardless of
``--verbose``, since none of them are ``jarvis``'s own code and
several would flood the terminal at DEBUG. Without ``--verbose``,
logging configuration is unchanged from every other subcommand's
existing (absent) behavior.

``send-email`` (2026-09-03) is the first real caller of
``jarvis.kernel.communications.authorize_and_send_email`` -- closing
exactly the "authorizable and proven, but no wired entry point" gap
M6a's own threat-model note named. A flat, top-level subcommand,
matching ``ping``/``read``/``play``'s own granularity (one capability,
one subcommand) rather than ``memory``'s nested-group shape (a family
of related subcommands introduced together) -- only ``send_email`` is
wired here, not ``list_email``/``read_email``/either calendar
capability, so a group would anticipate subcommands this pass does not
build. ``--imap-host``/``--smtp-host``/``--username``/
``--password-reference`` are new, required flags with no default, on
purpose -- mirroring ``authorize_and_send_email``'s own
``email_port``: which real mailbox to send through is real,
per-deployment configuration this module does not decide either,
exactly like ``listen``'s own ``Gtk4PhysicalConfirmationAdapter``, the
only other place this file constructs a real, concrete adapter itself
rather than letting a kernel function default one internally.
``authorize_and_send_email`` is ``async`` (``EmailPort.send_message``
is), so this branch is the second place (after ``listen``) that wraps
a kernel call in ``asyncio.run`` -- every other subcommand here calls
a synchronous kernel function directly.

``create-calendar-event`` (2026-09-03) is the identical wiring for
``jarvis.kernel.communications.authorize_and_create_calendar_event`` --
same flat, top-level shape as ``send-email``, same real-adapter-
construction-in-``cli`` reasoning (``--caldav-url``/``--username``/
``--password-reference`` construct a real ``CalDavCalendarAdapter``,
no default, ``calendar_port`` is real per-deployment config this
module does not decide either). ``--attendee`` is repeatable
(``action="append"``, default ``[]``) -- an event with zero, one, or
several real attendees is the same real distinction
``calendar_effect_for`` itself branches on (attendee-less floors
``WRITE_LOCAL``/``CONFIRM``; attendee-bearing floors through
``egress_effect_for``, same as email). A granted create's real new
``uid`` is printed, mirroring ``memory write``'s own ``identifier:``
line.

``code``/``draft`` (2026-09-04) are the first real CLI callers of
``jarvis.kernel.coding.authorize_and_run_coding_task``/
``jarvis.kernel.job_assistance.authorize_and_draft_document``, now that
both have a real, local-only default provider (see each module's own
docstring). Neither takes a cloud-provider override flag -- see
``_add_reasoning_parsers``'s own docstring for why building one here
would violate this project's own hard gate against configuring real
cloud-provider credentials unattended. Both wrap their kernel call in
``asyncio.run``, the same shape ``send-email``/``create-calendar-event``
already use.

``open-brave-url``/``open-vscode-file``/``send-claude-text``/
``send-chatgpt-text``/``list-docker-containers``/
``stop-docker-container``/``git-status``/``git-create-branch``/
``git-commit``/``git-push``/``git-force-push`` (real CLI wiring pass)
close the real "``kernel/desktop.py``'s capabilities are real but
never wired into this module" gap Track 6's own charter-completeness
re-check named. Eleven flat, top-level subcommands, one per distinct
``CapabilityId`` ``kernel/desktop.py`` already implements -- mirroring
``play``/``pause``/``next``/``previous``'s own "one subcommand per
capability" granularity, not a nested ``desktop <verb>`` shape.
``send-claude-text``/``send-chatgpt-text`` construct a real
``AtspiDesktopWindowAdapter()`` directly (see
``_run_desktop_app_subcommand``'s own docstring for why ``kernel``
itself cannot default one). **Two real capabilities are deliberately
absent, not overlooked**: ``terminal.run`` (needs
``SyntheticInputPort``, explicitly out of scope for the pass that
added this wiring) and ``docker.run_container``/``docker.build_image``
(DESTRUCTIVE-tier Docker actions, explicitly named "do not touch" by
that same pass's own hard gate) -- see
``_add_desktop_parsers``'s own docstring for the full reasoning.

**Real bug found and fixed (overnight hardening pass, 2026-09-04)**:
``main()``'s own ``except`` tuple never gained the six real,
adapter-level exception types the desktop-wiring pass's own new
subcommands can genuinely raise --
``BrowserLaunchFailedError``/``EditorLaunchFailedError``
(``ports/brave.py``/``ports/vscode.py``),
``WindowNotFoundError``/``WindowActionFailedError``
(``ports/desktop_window.py``, the two chat-app commands), and
``DockerCommandFailedError``/``GitCommandFailedError``
(``ports/docker.py``/``ports/git.py``). Confirmed as a real, not
theoretical, crash before fixing it: a granted ``send-chatgpt-text``
call whose real ``WindowNotFoundError`` was allowed to propagate
produced an unhandled Python traceback out of ``main()`` itself,
rather than this module's own established "print `Error: ...`, exit 1"
failure shape every other real-world error already gets. All six are
now caught -- see ``tests/unit/test_cli_main.py``'s own
"hardening pass" tests for the real, empirical proof.
"""

from __future__ import annotations

import argparse
import asyncio
import ctypes.util
import importlib.metadata
import logging
import os
import shutil
import sqlite3
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from jarvis.adapters.calendar import CalDavCalendarAdapter, CalendarEventCreationError
from jarvis.adapters.desktop_window import AtspiDesktopWindowAdapter
from jarvis.adapters.email import ImapEmailAdapter
from jarvis.adapters.memory import UnsupportedMemoryValueError
from jarvis.adapters.physical_confirmation import Gtk4PhysicalConfirmationAdapter
from jarvis.adapters.secret import SecretServiceAdapter
from jarvis.application.coding.loop import DEFAULT_MAX_CLIMBS
from jarvis.application.planning.executor import PlanValidationError
from jarvis.application.planning.planner import PlanningError
from jarvis.application.routing.router import RouteKind, RouteResult
from jarvis.cli.ui_server import UiServerConfig, create_server, run_ui_server
from jarvis.domain.browser import PageHandle
from jarvis.domain.errors import JarvisError
from jarvis.kernel.audit import authorize_and_view_audit_history
from jarvis.kernel.browser import (
    UnsupportedUrlSchemeError,
    authorize_and_capture_screenshot,
    authorize_and_close_page,
    authorize_and_open_page,
    authorize_and_query_dom,
)
from jarvis.kernel.coding import authorize_and_run_coding_task
from jarvis.kernel.communications import (
    authorize_and_create_calendar_event,
    authorize_and_list_calendar_events,
    authorize_and_list_email,
    authorize_and_read_email,
    authorize_and_send_email,
)
from jarvis.kernel.desktop import (
    ChatApp,
    authorize_and_commit_git,
    authorize_and_create_git_branch,
    authorize_and_force_push_git,
    authorize_and_get_git_status,
    authorize_and_list_docker_containers,
    authorize_and_open_brave_url,
    authorize_and_open_vscode_file,
    authorize_and_push_git,
    authorize_and_send_text_to_chat_app,
    authorize_and_stop_docker_container,
)
from jarvis.kernel.files import (
    PathOutsideAllowedScopeError,
    authorize_and_delete_file,
    authorize_and_find_files,
    authorize_and_list_dir,
    authorize_and_list_recent_files,
    authorize_and_move_file,
    authorize_and_read_file,
    authorize_and_search_content,
)
from jarvis.kernel.job_application import (
    VALID_JOB_APPLICATION_STATUSES,
    authorize_and_list_job_applications,
    authorize_and_record_job_application,
)
from jarvis.kernel.job_assistance import (
    ApplicationFolderAlreadyExistsError,
    ApplicationFolderOutsideBaseDirectoryError,
    authorize_and_draft_document,
    authorize_and_prepare_application_folder,
)
from jarvis.kernel.job_search import (
    JobSearchSite,
    authorize_and_find_careers_page,
    authorize_and_open_job_search,
)
from jarvis.kernel.memory import (
    authorize_and_backup_memory,
    authorize_and_forget,
    authorize_and_pin,
    authorize_and_recall,
    authorize_and_remember,
    authorize_and_restore_memory,
    authorize_and_wipe_memory,
)
from jarvis.kernel.music import MUSIC_COMMAND_NAMES, authorize_and_run_music_command
from jarvis.kernel.ping import authorize_ping
from jarvis.kernel.planning import authorize_and_run_plan
from jarvis.kernel.project import authorize_and_get_project_status, authorize_and_start_project
from jarvis.kernel.router import authorize_and_route
from jarvis.kernel.tasks import (
    STALE_RUNNING_THRESHOLD_SECONDS,
    VALID_TASK_STATUSES,
    authorize_and_cancel_task,
    authorize_and_create_task,
    authorize_and_get_task,
    authorize_and_list_tasks,
    authorize_and_recover_task,
    authorize_and_retry_task,
    authorize_and_run_task,
    authorize_and_schedule_task,
    filter_scheduled_tasks,
)
from jarvis.kernel.voice_loop import run_voice_loop
from jarvis.kernel.worker import run_pending_tasks_once
from jarvis.ports.brave import BrowserLaunchFailedError
from jarvis.ports.desktop_window import WindowActionFailedError, WindowNotFoundError
from jarvis.ports.docker import DockerCommandFailedError
from jarvis.ports.email import EmailConnectionError, EmailMessageNotFoundError
from jarvis.ports.git import GitCommandFailedError
from jarvis.ports.media_player import MediaPlayerCommandFailedError, NoMediaPlayerRunningError
from jarvis.ports.memory_write import MemoryRecordNotFoundError
from jarvis.ports.retrieval import MemoryIntegrityViolationError
from jarvis.ports.sandbox import SandboxUnavailableError
from jarvis.ports.secret import SecretNotFoundError
from jarvis.ports.vscode import EditorLaunchFailedError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from jarvis.application.planning.executor import PlanStepRecord
    from jarvis.domain.audit import AuditRecord
    from jarvis.domain.calendar import CalendarEvent
    from jarvis.domain.email import EmailMessage, EmailSummary
    from jarvis.domain.file_system import DirEntry
    from jarvis.domain.memory import MemoryRecord
    from jarvis.domain.policy import Decision
    from jarvis.domain.provenance import Tainted
    from jarvis.kernel.worker import WorkerPassOutcome

_DEFAULT_CHAIN_PATH = Path("audit_chain.json")
_DEFAULT_UI_PORT = 8765
_DEFAULT_WORKER_POLL_INTERVAL_SECONDS = 10.0
"""jarvis task worker's own default sleep between continuous-mode passes (WP-120) -- short
enough that a newly-created task is picked up promptly, long enough not to hammer the real
SQLite store/audit chain with an authorize_and_list_tasks call many times a second."""


def _non_negative_float(raw: str) -> float:
    """Argparse ``type=`` for ``--poll-interval-seconds`` (WP-152).

    A negative value previously reached ``time.sleep()`` unvalidated,
    raising a raw ``ValueError: sleep length must be non-negative`` --
    a real, unhandled crash, confirmed directly before this fix.
    Rejected here instead, with a clean, argparse-native error.
    """
    value = float(raw)
    if value < 0:
        msg = f"must be non-negative, got {value!r}"
        raise argparse.ArgumentTypeError(msg)
    return value


def _positive_int(raw: str) -> int:
    """Argparse ``type=`` for ``--max-passes`` (WP-152).

    Zero or negative previously made continuous mode's own ``while``
    loop condition false immediately -- the worker silently ran zero
    passes and exited 0, printing only its own "Running..." banner,
    with no indication anything unusual happened. Rejected here
    instead, with a clean, argparse-native error.
    """
    value = int(raw)
    if value < 1:
        msg = f"must be a positive integer, got {value!r}"
        raise argparse.ArgumentTypeError(msg)
    return value


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    """Add the confirmation/chain-path flags every subcommand shares."""
    parser.add_argument(
        "--physical-confirmation-available",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Whether a human is physically present to confirm (default: false).",
    )
    parser.add_argument(
        "--remote-confirmation-available",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Whether the action can be confirmed remotely (default: false).",
    )
    parser.add_argument(
        "--chain-path",
        type=Path,
        default=_DEFAULT_CHAIN_PATH,
        help=f"Where the audit chain is persisted (default: {_DEFAULT_CHAIN_PATH}).",
    )


def _add_communications_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the send-email/create-calendar-event/email/calendar subparsers.

    Split out to keep _build_parser lean.

    ``calendar list-events`` is a new, nested subcommand wiring one
    more already-real, already-tested, read-only (``Tier.ALLOW``)
    capability (`communications.list_calendar_events`) into the CLI
    for the first time -- a real, named gap re-confirmed directly
    (grepped `cli/main.py` for every real, registered
    `kernel/communications.py` composition function; this was the one
    genuinely missing) rather than assumed still-open from a stale
    prior finding. Reuses the identical real `CalDavCalendarAdapter`
    flags `create-calendar-event` already established
    (`--caldav-url`/`--username`/`--password-reference`).

    ``email list``/``email read`` are new, nested subcommands wiring
    two already-real, already-tested, read-only (``Tier.ALLOW``)
    capabilities (`communications.list_email`/`communications.read_email`)
    into the CLI for the first time -- a real, named gap from the
    adapter-failure-resilience pass. Both require the identical real
    ``ImapEmailAdapter`` flags ``send-email`` already established
    (``--imap-host``/``--smtp-host``/``--username``/``--password-reference``)
    -- ``ImapEmailAdapter``'s own real constructor requires
    ``smtp_host`` unconditionally, even though neither read-only
    command ever uses it, since one adapter class implements the
    port's full read+write surface.
    """
    send_email_parser = subparsers.add_parser(
        "send-email", help="Send a real email to one or more real recipients."
    )
    send_email_parser.add_argument("to", nargs="+", help="One or more real recipient addresses.")
    send_email_parser.add_argument("--subject", required=True, help="The real subject line.")
    send_email_parser.add_argument("--body", required=True, help="The real message body.")
    send_email_parser.add_argument(
        "--imap-host", required=True, help="The real IMAP server hostname."
    )
    send_email_parser.add_argument(
        "--smtp-host", required=True, help="The real SMTP server hostname."
    )
    send_email_parser.add_argument("--username", required=True, help="The real mailbox username.")
    send_email_parser.add_argument(
        "--password-reference",
        required=True,
        help=(
            "The keyring reference for this mailbox's password -- "
            "provisioned out of band, not by this command."
        ),
    )
    _add_common_flags(send_email_parser)

    create_event_parser = subparsers.add_parser(
        "create-calendar-event", help="Create a real calendar event, optionally with attendees."
    )
    create_event_parser.add_argument("--summary", required=True, help="The real event summary.")
    create_event_parser.add_argument(
        "--start", required=True, help="The real event start time (ISO-8601)."
    )
    create_event_parser.add_argument(
        "--end", required=True, help="The real event end time (ISO-8601)."
    )
    create_event_parser.add_argument(
        "--attendee",
        action="append",
        default=[],
        dest="attendees",
        help="A real attendee address. Repeatable for multiple attendees.",
    )
    create_event_parser.add_argument(
        "--caldav-url", required=True, help="The real CalDAV server URL."
    )
    create_event_parser.add_argument(
        "--username", required=True, help="The real CalDAV account username."
    )
    create_event_parser.add_argument(
        "--password-reference",
        required=True,
        help=(
            "The keyring reference for this account's password -- "
            "provisioned out of band, not by this command."
        ),
    )
    _add_common_flags(create_event_parser)

    email_parser = subparsers.add_parser("email", help="Real, read-only IMAP mailbox commands.")
    email_subparsers = email_parser.add_subparsers(dest="email_command", required=True)

    email_list_parser = email_subparsers.add_parser(
        "list", help="List real message summaries in a real IMAP folder."
    )
    email_list_parser.add_argument(
        "--folder", default="INBOX", help="The real IMAP folder to list (default: INBOX)."
    )
    email_list_parser.add_argument(
        "--limit", type=int, default=10, help="Maximum real summaries to return (default: 10)."
    )
    _add_email_connection_flags(email_list_parser)
    _add_common_flags(email_list_parser)

    email_read_parser = email_subparsers.add_parser(
        "read", help="Read one real message's full content by its real message id."
    )
    email_read_parser.add_argument("message_id", help="The real message's own id.")
    _add_email_connection_flags(email_read_parser)
    _add_common_flags(email_read_parser)

    calendar_parser = subparsers.add_parser(
        "calendar", help="Real, read-only CalDAV calendar commands."
    )
    calendar_subparsers = calendar_parser.add_subparsers(dest="calendar_command", required=True)

    calendar_list_events_parser = calendar_subparsers.add_parser(
        "list-events", help="List real events in a real, given time range."
    )
    calendar_list_events_parser.add_argument(
        "--start", required=True, help="The real range start (ISO-8601)."
    )
    calendar_list_events_parser.add_argument(
        "--end", required=True, help="The real range end (ISO-8601)."
    )
    calendar_list_events_parser.add_argument(
        "--caldav-url", required=True, help="The real CalDAV server URL."
    )
    calendar_list_events_parser.add_argument(
        "--username", required=True, help="The real CalDAV account username."
    )
    calendar_list_events_parser.add_argument(
        "--password-reference",
        required=True,
        help=(
            "The keyring reference for this account's password -- "
            "provisioned out of band, not by this command."
        ),
    )
    _add_common_flags(calendar_list_events_parser)


def _add_email_connection_flags(parser: argparse.ArgumentParser) -> None:
    """Add the real ImapEmailAdapter connection flags ``email list``/``email read`` both need.

    Split out from `_add_communications_parsers` purely because both
    subcommands need the identical, real four flags -- avoids
    repeating the same four `add_argument` calls twice.
    """
    parser.add_argument("--imap-host", required=True, help="The real IMAP server hostname.")
    parser.add_argument("--smtp-host", required=True, help="The real SMTP server hostname.")
    parser.add_argument("--username", required=True, help="The real mailbox username.")
    parser.add_argument(
        "--password-reference",
        required=True,
        help=(
            "The keyring reference for this mailbox's password -- "
            "provisioned out of band, not by this command."
        ),
    )


def _add_reasoning_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the code/draft subparsers -- both use the real, local-only default provider(s).

    Neither takes a cloud-provider override flag in this pass, on
    purpose: building one would mean wiring a real vendor-family
    adapter/model/keyring reference here, exactly the real
    cloud-provider configuration this project's own hard gate forbids
    doing unattended. A caller that wants real cloud escalation calls
    `authorize_and_run_coding_task`/`authorize_and_draft_document`
    directly with an explicit `dispatcher_factory`/`providers`,
    bypassing the CLI -- this is a real, deliberate scope limit, not an
    oversight.
    """
    code_parser = subparsers.add_parser(
        "code", help="Run a real, local-only coding-agent task against a target repository."
    )
    code_parser.add_argument("task", help="The real coding task's own plain-text description.")
    code_parser.add_argument("repo_path", type=Path, help="The real target repository.")
    code_parser.add_argument(
        "--max-climbs",
        type=int,
        default=DEFAULT_MAX_CLIMBS,
        help=f"The real ceiling on Dispatcher.run() climbs (default: {DEFAULT_MAX_CLIMBS}).",
    )
    _add_common_flags(code_parser)

    draft_parser = subparsers.add_parser(
        "draft",
        help="Draft a real document (e.g. a cover letter) using the real, local-only model.",
    )
    draft_parser.add_argument("task", help="The real drafting task's own plain-text description.")
    draft_parser.add_argument(
        "--drafts-dir",
        type=Path,
        default=None,
        help="Where the real drafted file is saved (default: ./drafts).",
    )
    _add_common_flags(draft_parser)


def _add_prepare_application_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the prepare-application subparser -- real, local-only application-folder drafting.

    No Overleaf integration of any kind (the user is on Overleaf's Free
    plan, which does not support git access) -- this only creates real,
    local folders, copies the user's own real template files verbatim,
    and drafts a real, separate cover-letter body fragment. Takes no
    cloud-provider override flag, the identical reasoning
    `_add_reasoning_parsers`'s own docstring already gives for
    `code`/`draft` (this reuses `job_assistance.draft` internally,
    unmodified).
    """
    prepare_parser = subparsers.add_parser(
        "prepare-application",
        help=(
            "Create a real, local CV/Cover Letter application folder from your own "
            "real templates, and draft a real cover-letter body fragment."
        ),
    )
    prepare_parser.add_argument("job_title", help="The real job title this application is for.")
    prepare_parser.add_argument("company", help="The real company name this application is for.")
    prepare_parser.add_argument(
        "--base-dir",
        type=Path,
        required=True,
        help="Your own real, chosen base directory for application folders. No default.",
    )
    prepare_parser.add_argument(
        "--month-label",
        required=True,
        help="The real month/year label, matching your own naming convention "
        '(e.g. "September 2026"). No default.',
    )
    prepare_parser.add_argument(
        "--cv-template",
        type=Path,
        required=True,
        help="Your own real, existing local CV template file. Copied verbatim.",
    )
    prepare_parser.add_argument(
        "--cover-letter-template",
        type=Path,
        required=True,
        help="Your own real, existing local cover-letter template file. Copied verbatim.",
    )
    prepare_parser.add_argument(
        "--task-description",
        default=None,
        help="Real, optional extra context for the drafted cover-letter body.",
    )
    prepare_parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Overwrite a real, already-existing application folder's own content. "
            "Without this, an existing folder fails cleanly rather than being touched."
        ),
    )
    prepare_parser.add_argument(
        "--record",
        action="store_true",
        help=(
            "After a granted folder creation, also record this application in the "
            "job-application ledger (status=drafted, folder=the real folder just "
            "created) -- one command instead of two for the common case. Without "
            "this, behavior is exactly as before: folder only, no ledger entry."
        ),
    )
    _add_common_flags(prepare_parser)


def _add_job_application_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the job-application subparser -- a real, thin memory.write/memory.retrieve convention.

    Mirrors ``memory``/``plan``'s own nested-subcommand shape (see
    ``docs/OPEN_DECISIONS.md``'s own item 4). Neither ``record`` nor
    ``list`` is a new capability -- both dispatch straight to
    ``jarvis.kernel.job_application``, which itself reuses
    ``authorize_and_remember``/``authorize_and_recall`` unmodified.
    """
    job_application_parser = subparsers.add_parser(
        "job-application", help="Track applied job roles as structured memories."
    )
    job_application_subparsers = job_application_parser.add_subparsers(
        dest="job_application_command", required=True
    )

    record_parser = job_application_subparsers.add_parser(
        "record", help="Record one applied job role."
    )
    record_parser.add_argument("company", help="The real company name.")
    record_parser.add_argument("role", help="The real role/job title.")
    record_parser.add_argument(
        "--status",
        required=True,
        choices=VALID_JOB_APPLICATION_STATUSES,
        help="The real, current status of this application.",
    )
    record_parser.add_argument(
        "--folder",
        default=None,
        help=(
            "The real, local application-folder path from "
            "'prepare-application', if this application has one. "
            "Omit if recorded manually."
        ),
    )
    record_parser.add_argument("--notes", default=None, help="Real, optional free-text notes.")
    _add_common_flags(record_parser)

    list_parser = job_application_subparsers.add_parser(
        "list", help="List recorded job applications, optionally filtered by status."
    )
    list_parser.add_argument(
        "--status",
        default=None,
        choices=VALID_JOB_APPLICATION_STATUSES,
        help="Only show applications with this exact status.",
    )
    _add_common_flags(list_parser)


def _add_planning_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add the plan run subparser -- a real, invocable planning.run_plan (ADR-0062), nested.

    Mirrors ``memory``'s own nested-subcommand shape (the one real,
    already-accepted precedent for this in this file, per
    ``docs/OPEN_DECISIONS.md``'s own item 4 -- kept, not renamed).
    Takes no cloud-provider override flag, on purpose, the identical
    reasoning ``_add_reasoning_parsers``'s own docstring already gives
    for ``code``/``draft``: real vendor-family cloud configuration is
    out of this CLI's own scope. Omitting ``provider`` reaches
    ``authorize_and_run_plan``'s own real, local-only default, which
    now logs a real, honest warning about that default's own known
    reliability gap (`kernel/planning.py`'s own module docstring).
    """
    plan_parser = subparsers.add_parser("plan", help="Task-planning commands.")
    plan_subparsers = plan_parser.add_subparsers(dest="plan_command", required=True)

    plan_run_parser = plan_subparsers.add_parser(
        "run", help="Propose and run a real, multi-step plan for a goal."
    )
    plan_run_parser.add_argument("goal", help="The real, natural-language goal to plan for.")
    _add_common_flags(plan_run_parser)


def _add_project_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add project start/status -- a typed-goal workflow atop planning.run_plan, nested.

    Mirrors ``job-application``'s own nested-subcommand shape exactly.
    Omits a cloud-provider override flag, on purpose, the identical
    reasoning ``_add_planning_parsers``'s own docstring already gives:
    real vendor-family cloud configuration is out of this CLI's own
    scope. Omitting ``provider`` reaches
    ``authorize_and_start_project``'s own real, local-only default via
    ``authorize_and_run_plan`` unmodified, including that default's own
    real, honest reliability warning.
    """
    project_parser = subparsers.add_parser("project", help="Typed project-goal workflow commands.")
    project_subparsers = project_parser.add_subparsers(dest="project_command", required=True)

    start_parser = project_subparsers.add_parser(
        "start", help="Start a real, multi-step plan for a typed project goal."
    )
    start_parser.add_argument("goal", help="The real, natural-language project goal.")
    _add_common_flags(start_parser)

    status_parser = project_subparsers.add_parser(
        "status", help="Retrieve the most recent real status recorded for a project goal."
    )
    status_parser.add_argument(
        "goal", help="The exact goal string previously passed to 'project start'."
    )
    _add_common_flags(status_parser)


def _add_task_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add task create/run/status/list -- the real, general Task/TaskStore (WP-107), nested.

    Mirrors ``project``'s own nested-subcommand shape. Deliberately
    two separate verbs, ``create`` and ``run``, rather than one
    combined command -- see ``kernel/tasks.py``'s own module docstring
    for why a later background-execution layer needs a real task id
    returned before a plan finishes running, which a single,
    monolithic command cannot support. ``jarvis project start``
    remains the one-shot convenience command for callers that don't
    need the split.
    """
    task_parser = subparsers.add_parser("task", help="Persistent task commands.")
    task_subparsers = task_parser.add_subparsers(dest="task_command", required=True)

    create_parser = task_subparsers.add_parser(
        "create", help="Create a new real task, status 'created'. Does not run any plan."
    )
    create_parser.add_argument("goal", help="The real, natural-language task goal.")
    _add_common_flags(create_parser)

    run_parser = task_subparsers.add_parser(
        "run", help="Run planning.run_plan for an already-created task."
    )
    run_parser.add_argument("task_id", help="A real identifier from a prior 'task create'.")
    run_parser.add_argument("goal", help="The same real goal that task was created for.")
    _add_common_flags(run_parser)

    status_parser = task_subparsers.add_parser(
        "status", help="Look up one real task by its own identifier."
    )
    status_parser.add_argument("task_id", help="A real identifier from a prior 'task create'.")
    _add_common_flags(status_parser)

    list_parser = task_subparsers.add_parser(
        "list", help="List real tasks, optionally filtered by status."
    )
    list_filter_group = list_parser.add_mutually_exclusive_group()
    list_filter_group.add_argument(
        "--status",
        default=None,
        choices=VALID_TASK_STATUSES,
        help="Only show tasks with this exact status.",
    )
    list_filter_group.add_argument(
        "--scheduled-only",
        action="store_true",
        help=(
            "Only show real, currently-scheduled tasks -- a 'created' task with a real "
            "scheduled_at. Mutually exclusive with --status, since a scheduled task is "
            "always 'created'."
        ),
    )
    _add_common_flags(list_parser)

    cancel_parser = task_subparsers.add_parser(
        "cancel",
        help=(
            "Cancel a real task still 'created' or 'running' (WP-117). Does not interrupt "
            "any in-flight execution -- there is none to interrupt in this architecture."
        ),
    )
    cancel_parser.add_argument("task_id", help="A real identifier from a prior 'task create'.")
    _add_common_flags(cancel_parser)

    recover_parser = task_subparsers.add_parser(
        "recover",
        help=(
            "Recover a real task stuck 'running' past the staleness threshold (WP-126), "
            "e.g. after its owning process crashed. Refuses outright unless the task is "
            "genuinely stale (see 'task status'). Transitions it to 'failed' via a real "
            "compare-and-swap, after which 'task retry' works normally."
        ),
    )
    recover_parser.add_argument("task_id", help="A real identifier from a prior 'task create'.")
    _add_common_flags(recover_parser)

    retry_parser = task_subparsers.add_parser(
        "retry",
        help=(
            "Explicitly retry a real task currently 'failed' (WP-121). Delegates to the "
            "same, unmodified execution path as 'task run' -- no new authorization, no "
            "new claim mechanism."
        ),
    )
    retry_parser.add_argument("task_id", help="A real identifier from a prior 'task create'.")
    _add_common_flags(retry_parser)

    schedule_parser = task_subparsers.add_parser(
        "schedule",
        help=(
            "Schedule a real task still 'created' to become due at a future time (WP-122). "
            "Does not change the task's own status; the existing worker claims and runs it "
            "once its own scheduled time has passed."
        ),
    )
    schedule_parser.add_argument("task_id", help="A real identifier from a prior 'task create'.")
    schedule_parser.add_argument(
        "--at",
        dest="scheduled_at",
        required=True,
        help=(
            "A real ISO-8601 timestamp with an explicit timezone offset "
            "(e.g. '2026-09-12T09:00:00+00:00' or '...Z') -- naive timestamps are rejected."
        ),
    )
    _add_common_flags(schedule_parser)

    worker_parser = task_subparsers.add_parser(
        "worker",
        help=(
            "Discover every real 'created' task and claim-and-run each through the "
            "canonical task execution path (WP-120). Foreground by default; no hidden "
            "daemonization."
        ),
    )
    worker_parser.add_argument(
        "--once",
        action="store_true",
        help="Run exactly one pass over currently-eligible tasks, then exit (default: false).",
    )
    worker_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Show which real 'created' tasks are currently eligible/due, without claiming or "
            "running any of them -- never executes anything, takes priority over --once/"
            "--max-passes/--poll-interval-seconds if given."
        ),
    )
    worker_parser.add_argument(
        "--poll-interval-seconds",
        type=_non_negative_float,
        default=_DEFAULT_WORKER_POLL_INTERVAL_SECONDS,
        help=(
            "Seconds to sleep between passes in continuous mode (ignored with --once); "
            f"default: {_DEFAULT_WORKER_POLL_INTERVAL_SECONDS}. Must be non-negative."
        ),
    )
    worker_parser.add_argument(
        "--max-passes",
        type=_positive_int,
        default=None,
        help=(
            "Stop after this many passes in continuous mode (ignored with --once) -- a real, "
            "deterministic alternative to Ctrl+C for scripted or automated runs. Unbounded "
            "if omitted. Must be a positive integer."
        ),
    )
    _add_common_flags(worker_parser)


def _add_do_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add `do` -- WP-104's one, canonical typed freeform command router entry point.

    A single, flat, top-level subcommand (mirroring
    `ping`/`read`/`play`'s own granularity), not a nested group --
    there is exactly one real verb here. Deliberately the only name
    added (the prompt's own "do not add multiple aliases just for
    convenience" instruction): `do` reads as "go act on this," which
    matches what a granted route actually causes (executing a
    deterministic command, or creating a task) better than `ask`,
    which reads as a question-answering interface this is not.
    """
    do_parser = subparsers.add_parser(
        "do",
        help="Route a typed, natural-language request (WP-104).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples of deterministically recognized requests\n"
            "(matched before any reasoning fallback; see\n"
            "docs/protocol/README.md for the full, current list):\n"
            '  jarvis do "recall my notes on the interview"\n'
            '  jarvis do "remember the wifi password is..."\n'
            '  jarvis do "read ~/todo.txt"\n'
            '  jarvis do "find files *.py"\n'
            '  jarvis do "search files TODO"\n'
            '  jarvis do "recent files"\n'
            '  jarvis do "task status <task-id>"\n'
            '  jarvis do "list tasks"\n'
            '  jarvis do "list scheduled tasks"\n'
            "\n"
            "A request that matches none of these falls back to a real\n"
            "reasoning provider; one matching no real, wired capability at\n"
            "all is reported back, never executed."
        ),
    )
    do_parser.add_argument("text", help="The real, typed natural-language request.")
    _add_common_flags(do_parser)


def _add_browser_handle_flags(parser: argparse.ArgumentParser) -> None:
    """Add the four real PageHandle fields as required flags.

    Every ``jarvis`` invocation is a fresh, separate process (no
    shared in-memory adapter state -- see ``domain/browser.py``'s own
    module docstring), so ``screenshot``/``inspect-dom``/``close``
    each need a real, already-open page's own handle reconstructed
    from its four explicit fields, printed by a prior ``browser open``
    call, rather than an opaque, unreconstructable in-process
    reference.
    """
    parser.add_argument("--debug-port", type=int, required=True, help="From a prior 'open'.")
    parser.add_argument("--target-id", required=True, help="From a prior 'open'.")
    parser.add_argument("--process-id", type=int, required=True, help="From a prior 'open'.")
    parser.add_argument("--user-data-dir", required=True, help="From a prior 'open'.")


def _add_browser_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add the browser subparser -- real, invocable browser.open_page/screenshot/inspect_dom/close.

    Mirrors ``memory``/``plan``/``job-application``'s own nested
    shape: a family of four related actions on a real, CDP-controlled
    browser page, not a single action. No new capability -- all four
    already exist, real, tested, and used internally (by
    ``job_search.open_results``, the coding agent's own browser use),
    but previously had no CLI entry point of their own (a real, named
    gap from the dead-code sweep).
    """
    browser_parser = subparsers.add_parser(
        "browser", help="Real, CDP-controlled browser-page automation."
    )
    browser_subparsers = browser_parser.add_subparsers(dest="browser_command", required=True)

    open_parser = browser_subparsers.add_parser(
        "open", help="Open a real, dedicated, headless browser page navigated to a URL."
    )
    open_parser.add_argument("url", help="The real URL to navigate to.")
    _add_common_flags(open_parser)

    screenshot_parser = browser_subparsers.add_parser(
        "screenshot", help="Capture a real screenshot of an already-open page."
    )
    _add_browser_handle_flags(screenshot_parser)
    screenshot_parser.add_argument(
        "--output", type=Path, required=True, help="Where the real PNG bytes are written."
    )
    _add_common_flags(screenshot_parser)

    inspect_dom_parser = browser_subparsers.add_parser(
        "inspect-dom", help="Query an already-open page's live DOM for one element's outer HTML."
    )
    _add_browser_handle_flags(inspect_dom_parser)
    inspect_dom_parser.add_argument("--selector", required=True, help="A real CSS selector.")
    _add_common_flags(inspect_dom_parser)

    close_parser = browser_subparsers.add_parser(
        "close", help="Terminate an already-open page's real browser subprocess."
    )
    _add_browser_handle_flags(close_parser)
    _add_common_flags(close_parser)


def _add_job_search_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the job-search/find-careers-page subparsers -- both real, flat, assisted-browsing only.

    Mirrors ``open-brave-url``'s own flat-subcommand shape, not
    ``plan``/``memory``'s nested one -- each is a single action, not a
    family of related subcommands. Both open a real, real-only URL in
    the user's own, real, ordinary Brave browser for the user to
    search/read themselves -- neither reads, scrapes, or extracts any
    page content (see ``kernel/job_search.py``'s own module docstring
    for the full, real reasoning, including why ``find-careers-page``
    uses DuckDuckGo rather than Google).
    """
    job_search_parser = subparsers.add_parser(
        "job-search", help="Open a real LinkedIn/Indeed job-search results page in Brave."
    )
    job_search_parser.add_argument("keywords", help="The real search keywords.")
    job_search_parser.add_argument(
        "--site",
        required=True,
        choices=[site.value for site in JobSearchSite],
        help="Which job board to search.",
    )
    job_search_parser.add_argument(
        "--location", default=None, help="An optional real location filter."
    )
    _add_common_flags(job_search_parser)

    careers_parser = subparsers.add_parser(
        "find-careers-page",
        help="Open a real '<company> careers' search (DuckDuckGo) in Brave.",
    )
    careers_parser.add_argument("company", help="The real company name.")
    _add_common_flags(careers_parser)


def _add_file_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add the list-dir/move-file/delete-file subparsers (ADR-0060).

    All three use the real default `allowed_root` (`Path.home()`) --
    no CLI flag overrides it, mirroring `fs.read_file`'s own existing
    `authorize_and_read_file` precedent exactly (no `--allowed-root`
    flag exists for `read` either).
    """
    list_dir_parser = subparsers.add_parser(
        "list-dir", help="List a real local directory's entries, scoped to the allowed root."
    )
    list_dir_parser.add_argument("path", type=Path, help="The real directory to list.")
    _add_common_flags(list_dir_parser)

    move_file_parser = subparsers.add_parser(
        "move-file", help="Move a real local file or directory, both endpoints scope-checked."
    )
    move_file_parser.add_argument("source", type=Path, help="The real file/directory to move.")
    move_file_parser.add_argument("destination", type=Path, help="Where to move it to.")
    _add_common_flags(move_file_parser)

    delete_file_parser = subparsers.add_parser(
        "delete-file", help="Permanently delete a single real local file. Always MANUAL_ONLY."
    )
    delete_file_parser.add_argument("path", type=Path, help="The real file to delete.")
    _add_common_flags(delete_file_parser)


def _add_fs_search_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add the fs find/search-content/recent subparsers -- real, recursive fs.* search commands.

    A real, third, deliberately-introduced CLI naming shape, reported
    plainly rather than silently added: `list-dir`/`move-file`/
    `delete-file` are flat, and `memory`/`plan`/`job-application` are
    nested groups whose CHILD names ARE their own verbs (`write`,
    `run`, `record`). This adds a third, `fs <verb>`, grouping three
    real, related, recursive search actions under one real namespace,
    distinct from the already-decided-to-leave-as-is inconsistencies
    `docs/OPEN_DECISIONS.md` item 4 already names (`memory`'s own
    nested shape, `fs.read_file`'s own bare `read`) -- this is a new,
    deliberate choice for this addition specifically, not a fix to
    either of those.
    """
    fs_parser = subparsers.add_parser(
        "fs", help="Recursive local-file search, scoped to allowed_root."
    )
    fs_subparsers = fs_parser.add_subparsers(dest="fs_command", required=True)

    find_parser = fs_subparsers.add_parser(
        "find", help="Search real filenames by glob pattern, recursively."
    )
    find_parser.add_argument("pattern", help="A real glob pattern, e.g. '*.py' or '**/test_*.py'.")
    _add_common_flags(find_parser)

    search_content_parser = fs_subparsers.add_parser(
        "search-content", help="Grep-style real file-content search, recursively, bounded."
    )
    search_content_parser.add_argument("query", help="A real, literal substring to search for.")
    _add_common_flags(search_content_parser)

    recent_parser = fs_subparsers.add_parser(
        "recent", help="List the most recently modified real files, recursively."
    )
    recent_parser.add_argument(
        "--limit", type=int, default=20, help="Maximum files to return (default: 20)."
    )
    _add_common_flags(recent_parser)


_CLAUDE_APP_LAUNCH_COMMAND = ("claude-desktop",)
"""The one real, confirmed launch command for the Claude desktop app.

Mirrors `kernel/desktop.py`'s own module-level note: confirmed against
a real, installed `claude-desktop` binary during WP-43's spike. No
equivalent exists for the ChatGPT app (never found installed), so
`send-chatgpt-text` passes `launch_command=None` -- an honest "no
confirmed default", not a guess.
"""


def _add_desktop_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add the desktop.*/docker.*/git.* subparsers wiring kernel/desktop.py's real capabilities.

    Two real capabilities are deliberately NOT wired here: `terminal.run`
    (needs `SyntheticInputPort`, explicitly out of scope -- untouched
    per this pass's own hard gate) and `docker.run_container`/
    `docker.build_image` (DESTRUCTIVE-tier Docker actions, explicitly
    named "do not touch" by this pass's own hard gate). Every other
    real `kernel/desktop.py` capability gets its own flat subcommand,
    mirroring `play`/`pause`/`next`/`previous`'s own "one subcommand
    per distinct CapabilityId" precedent, not a nested `desktop <verb>`
    shape.
    """
    open_brave_parser = subparsers.add_parser(
        "open-brave-url", help="Launch or focus Brave, navigated to a URL."
    )
    open_brave_parser.add_argument("url", help="The URL to open.")
    _add_common_flags(open_brave_parser)

    open_vscode_parser = subparsers.add_parser(
        "open-vscode-file", help="Launch or focus VS Code, opened to a file."
    )
    open_vscode_parser.add_argument("path", help="The file path to open.")
    _add_common_flags(open_vscode_parser)

    send_claude_parser = subparsers.add_parser(
        "send-claude-text", help="Type text into the Claude desktop app's input box."
    )
    send_claude_parser.add_argument("text", help="The text to type.")
    _add_common_flags(send_claude_parser)

    send_chatgpt_parser = subparsers.add_parser(
        "send-chatgpt-text", help="Type text into the ChatGPT desktop app's input box."
    )
    send_chatgpt_parser.add_argument("text", help="The text to type.")
    _add_common_flags(send_chatgpt_parser)

    list_docker_parser = subparsers.add_parser(
        "list-docker-containers", help="List every Docker container's name, read-only."
    )
    _add_common_flags(list_docker_parser)

    stop_docker_parser = subparsers.add_parser(
        "stop-docker-container", help="Stop a running Docker container -- recoverable."
    )
    stop_docker_parser.add_argument("container", help="The container's name or id.")
    _add_common_flags(stop_docker_parser)

    git_status_parser = subparsers.add_parser(
        "git-status", help="Show a git repository's working-tree status, read-only."
    )
    git_status_parser.add_argument("repo_dir", type=Path, help="The real git repository.")
    _add_common_flags(git_status_parser)

    git_create_branch_parser = subparsers.add_parser(
        "git-create-branch", help="Create and switch to a new git branch."
    )
    git_create_branch_parser.add_argument("repo_dir", type=Path, help="The real git repository.")
    git_create_branch_parser.add_argument("branch_name", help="The new branch's name.")
    _add_common_flags(git_create_branch_parser)

    git_commit_parser = subparsers.add_parser(
        "git-commit", help="Commit already-tracked, modified files."
    )
    git_commit_parser.add_argument("repo_dir", type=Path, help="The real git repository.")
    git_commit_parser.add_argument("message", help="The commit message.")
    _add_common_flags(git_commit_parser)

    git_push_parser = subparsers.add_parser(
        "git-push", help="An ordinary fast-forward push to a branch you already own."
    )
    git_push_parser.add_argument("repo_dir", type=Path, help="The real git repository.")
    git_push_parser.add_argument("remote", help="The remote name (e.g. origin).")
    git_push_parser.add_argument("branch", help="The branch to push.")
    _add_common_flags(git_push_parser)

    git_force_push_parser = subparsers.add_parser(
        "git-force-push", help="A force-push. Always MANUAL_ONLY -- no undo."
    )
    git_force_push_parser.add_argument("repo_dir", type=Path, help="The real git repository.")
    git_force_push_parser.add_argument("remote", help="The remote name (e.g. origin).")
    git_force_push_parser.add_argument("branch", help="The branch to force-push.")
    _add_common_flags(git_force_push_parser)


def _build_parser() -> argparse.ArgumentParser:  # noqa: PLR0915 -- one add_parser block per subcommand
    """Build the argument parser: one subcommand per authorizable command."""
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="Authorize (and, if granted, run) one capability call.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {importlib.metadata.version('jarvis')}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ping_parser = subparsers.add_parser("ping", help='Authorize the no-op "ping" capability.')
    _add_common_flags(ping_parser)

    audit_history_parser = subparsers.add_parser(
        "audit-history", help="View the real, persisted audit chain's own history."
    )
    audit_history_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Return at most this many of the most recent records.",
    )
    audit_history_parser.add_argument(
        "--capability-id",
        default=None,
        help="Only show records for this exact capability id (e.g. 'git.status').",
    )
    _add_common_flags(audit_history_parser)

    play_parser = subparsers.add_parser("play", help="Resume playback.")
    _add_common_flags(play_parser)

    pause_parser = subparsers.add_parser("pause", help="Pause playback.")
    _add_common_flags(pause_parser)

    next_parser = subparsers.add_parser("next", help="Skip to the next track.")
    _add_common_flags(next_parser)

    previous_parser = subparsers.add_parser("previous", help="Go back to the previous track.")
    _add_common_flags(previous_parser)

    read_parser = subparsers.add_parser(
        "read", help="Read a local file's contents (scoped to your home directory)."
    )
    read_parser.add_argument("path", type=Path, help="The file to read.")
    _add_common_flags(read_parser)

    memory_parser = subparsers.add_parser("memory", help="Memory-related commands.")
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command", required=True)

    memory_write_parser = memory_subparsers.add_parser("write", help="Memorize a piece of text.")
    memory_write_parser.add_argument("text", help="The text to memorize.")
    _add_common_flags(memory_write_parser)

    memory_retrieve_parser = memory_subparsers.add_parser(
        "retrieve", help="Search previously-memorized content."
    )
    memory_retrieve_parser.add_argument("query", help="The search text.")
    memory_retrieve_parser.add_argument(
        "--limit", type=int, default=5, help="Maximum records to return (default: 5)."
    )
    _add_common_flags(memory_retrieve_parser)

    memory_forget_parser = memory_subparsers.add_parser(
        "forget", help="Permanently delete a memorized record by identifier."
    )
    memory_forget_parser.add_argument("identifier", help="The record's identifier.")
    _add_common_flags(memory_forget_parser)

    memory_pin_parser = memory_subparsers.add_parser(
        "pin", help="Mark a memorized record as pinned -- never expires automatically."
    )
    memory_pin_parser.add_argument("identifier", help="The record's identifier.")
    _add_common_flags(memory_pin_parser)

    memory_backup_parser = memory_subparsers.add_parser(
        "backup", help="Copy the real, complete memory store to a chosen path."
    )
    memory_backup_parser.add_argument(
        "destination", type=Path, help="Where the real, live-safe copy is written."
    )
    _add_common_flags(memory_backup_parser)

    memory_restore_parser = memory_subparsers.add_parser(
        "restore",
        help="Replace the live memory store's entire content with a backup's. Always MANUAL_ONLY.",
    )
    memory_restore_parser.add_argument(
        "source", type=Path, help="A real, previously-created backup file."
    )
    _add_common_flags(memory_restore_parser)

    memory_wipe_parser = memory_subparsers.add_parser(
        "wipe",
        help="Permanently delete every record in the memory store. Always MANUAL_ONLY.",
    )
    _add_common_flags(memory_wipe_parser)

    _add_communications_parsers(subparsers)
    _add_reasoning_parsers(subparsers)
    _add_file_parsers(subparsers)
    _add_fs_search_parsers(subparsers)
    _add_desktop_parsers(subparsers)
    _add_planning_parsers(subparsers)
    _add_project_parsers(subparsers)
    _add_task_parsers(subparsers)
    _add_do_parsers(subparsers)
    _add_browser_parsers(subparsers)
    _add_job_search_parsers(subparsers)
    _add_prepare_application_parsers(subparsers)
    _add_job_application_parsers(subparsers)

    subparsers.add_parser(
        "doctor",
        help="Check this machine's real environment readiness -- no capability, no audit record.",
    )

    listen_parser = subparsers.add_parser(
        "listen",
        help="Run the voice pipeline continuously in the foreground, until interrupted.",
    )
    listen_parser.add_argument(
        "--chain-path",
        type=Path,
        default=_DEFAULT_CHAIN_PATH,
        help=f"Where the audit chain is persisted (default: {_DEFAULT_CHAIN_PATH}).",
    )
    listen_parser.add_argument(
        "--verbose",
        action="store_true",
        help=(
            "Enable DEBUG-level diagnostic logging for jarvis's own loggers "
            "(wake-word scores, VAD/STT/intent-resolution output). Third-party "
            "library loggers are left at their default level."
        ),
    )

    ui_parser = subparsers.add_parser(
        "ui",
        help=(
            "Serve the JARVIS UI foundation (WP-108) on 127.0.0.1, until interrupted. "
            "No --host flag exists, on purpose -- see jarvis.cli.ui_server's own module "
            "docstring."
        ),
    )
    ui_parser.add_argument(
        "--port",
        type=int,
        default=_DEFAULT_UI_PORT,
        help=f"Which localhost port to serve on (default: {_DEFAULT_UI_PORT}).",
    )
    ui_parser.add_argument(
        "--chain-path",
        type=Path,
        default=_DEFAULT_CHAIN_PATH,
        help=f"Where the audit chain is persisted (default: {_DEFAULT_CHAIN_PATH}).",
    )
    ui_parser.add_argument(
        "--database-path",
        type=Path,
        default=None,
        help="Where the real memory store lives (default: the same as every other subcommand's).",
    )
    ui_parser.add_argument(
        "--physical-confirmation-available",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Applied to every request this server handles for as long as it runs "
            "(default: false) -- not per-request. See UiServerConfig's own docstring."
        ),
    )
    ui_parser.add_argument(
        "--remote-confirmation-available",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="As --physical-confirmation-available, applied uniformly for the server's lifetime.",
    )
    ui_parser.add_argument(
        "--email-imap-host",
        default=None,
        help=(
            "The real IMAP server hostname (WP-114) -- optional; enables 'list emails'/"
            "'read email <id>' through this server when supplied together with "
            "--email-smtp-host/--email-username/--email-password-reference. Omitted by "
            "default, matching every other real port/credential flag's own 'no implicit "
            "default' precedent."
        ),
    )
    ui_parser.add_argument(
        "--email-smtp-host", default=None, help="The real SMTP server hostname (WP-114)."
    )
    ui_parser.add_argument(
        "--email-username", default=None, help="The real mailbox username (WP-114)."
    )
    ui_parser.add_argument(
        "--email-password-reference",
        default=None,
        help="The keyring reference for the mailbox's password (WP-114), provisioned out of band.",
    )
    ui_parser.add_argument(
        "--calendar-caldav-url",
        default=None,
        help=(
            "The real CalDAV server URL (WP-114) -- optional; enables 'what's on my "
            "calendar today/tomorrow/this week' through this server when supplied "
            "together with --calendar-username/--calendar-password-reference."
        ),
    )
    ui_parser.add_argument(
        "--calendar-username", default=None, help="The real CalDAV account username (WP-114)."
    )
    ui_parser.add_argument(
        "--calendar-password-reference",
        default=None,
        help="The keyring reference for the CalDAV account's password (WP-114).",
    )

    return parser


def _configure_logging(*, verbose: bool) -> None:
    """Establish a baseline logging config, then optionally raise jarvis's own loggers.

    The baseline (``WARNING``, root-wide) is unconditional so behavior
    is identical to today's unconfigured default for every existing
    subcommand -- Python's own ``logging.lastResort`` handler already
    surfaces WARNING+ with no configuration at all, so this is not new
    output, just an explicit equivalent of it. The ``"jarvis"`` logger
    (the common ancestor of every ``jarvis.*`` module logger) is always
    explicitly set, to ``DEBUG`` or back to ``WARNING`` depending on
    ``verbose`` -- never left at whatever a previous call happened to
    leave it, since ``logging.getLogger("jarvis")`` is a process-wide
    singleton and this function is not guaranteed to run only once per
    process (e.g. repeated calls within one test session). Third-party
    loggers, which are not descendants of ``"jarvis"``, are untouched
    either way and stay quiet.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    logging.getLogger("jarvis").setLevel(logging.DEBUG if verbose else logging.WARNING)


def _check_python_version() -> tuple[str, bool, str]:
    ok = sys.version_info >= (3, 12)
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return "Python version", ok, f"{version} (>=3.12 required)"


def _check_binary(name: str, *, why: str) -> tuple[str, bool, str]:
    path = shutil.which(name)
    return f"'{name}' binary", path is not None, path if path is not None else f"not found ({why})"


def _check_gtk4() -> tuple[str, bool, str]:
    try:
        import gi  # noqa: PLC0415 -- deliberately lazy, this is the real check itself

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk  # noqa: F401, PLC0415 -- import itself is the real check
    except (ImportError, ValueError) as exc:
        return "GTK4 typelib", False, f"not importable ({exc})"
    return "GTK4 typelib", True, "importable (confirmation dialogs / Console UI)"


def _check_portaudio() -> tuple[str, bool, str]:
    found = ctypes.util.find_library("portaudio")
    detail = found if found is not None else "not found (needed for real microphone capture)"
    return "libportaudio", found is not None, detail


def _check_ollama_reachable() -> tuple[str, bool, str]:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1)
    except OSError as exc:
        return "Ollama (localhost:11434)", False, f"not reachable ({exc})"
    return (
        "Ollama (localhost:11434)",
        True,
        "reachable (used by coding.run_task/job_assistance.draft's local-only default)",
    )


def _check_audit_chain_directory_writable() -> tuple[str, bool, str]:
    default_dir = _DEFAULT_CHAIN_PATH.resolve().parent
    ok = os.access(default_dir, os.W_OK)
    return (
        f"Default audit-chain directory ({default_dir})",
        ok,
        "writable" if ok else "not writable",
    )


def _check_memory_database_accessible() -> tuple[str, bool, str]:
    """Check the real, default memory/task-store database -- read-only, no side effects.

    WP-147: a deliberately narrow, safe check -- `sqlite3.connect`
    against a non-existent path silently creates an empty file, which
    a read-only diagnostic must never do, so a missing file is
    reported as a real, honest, non-failing informational state, not
    probed further. An existing file is opened strictly read-only
    (``mode=ro``) and a trivial query run against it, catching real
    corruption/permission issues a bare directory-writability check
    would miss (mirrors the real, documented `sqlite3.DatabaseError`
    finding from this project's own "Phase 2" resilience pass).
    """
    default_path = Path("memory.sqlite3").resolve()
    label = f"Default memory/task-store database ({default_path})"
    if not default_path.exists():
        return (label, True, "not yet created -- will be created on first write")
    try:
        with sqlite3.connect(f"file:{default_path}?mode=ro", uri=True) as connection:
            # A bare `SELECT 1` is a constant expression -- SQLite never touches the
            # real file's own schema/b-tree to answer it, so it would not actually
            # detect a garbage, non-SQLite file (confirmed empirically before fixing).
            # Querying the real sqlite_master schema table forces SQLite to validate
            # the file's own header/format for real.
            connection.execute("SELECT name FROM sqlite_master LIMIT 1")
    except sqlite3.Error as exc:
        return (label, False, f"exists but not accessible ({exc})")
    return (label, True, "accessible")


def _run_doctor() -> int:
    """Check this machine's real environment readiness. Always returns 0.

    **Real, deliberate design choice, not an oversight**: `doctor` is
    not a capability. It performs no action and reads no sensitive
    data -- only already-public, non-secret local environment facts
    (binary presence on `PATH`, Python version, GPU/GTK4/audio library
    availability, whether a local Ollama server is reachable) -- so it
    has no real `Effect` in this project's own taxonomy, and produces
    no audit record, the same way a bare `jarvis --help` needs no
    authorization either. Every check here is read-only and safe to
    run repeatedly.
    """
    print("jarvis doctor -- real environment readiness checks\n")
    checks = [
        _check_python_version(),
        _check_binary("git", why="needed for git.* desktop-control capabilities"),
        _check_binary("docker", why="needed for docker.* desktop-control capabilities"),
        _check_binary("bwrap", why="needed for the sandboxed coding agent"),
        _check_gtk4(),
        _check_portaudio(),
        _check_binary(
            "nvidia-smi", why="needed for real STT -- adapters/stt.py hardcodes device=cuda"
        ),
        _check_ollama_reachable(),
        _check_audit_chain_directory_writable(),
        _check_memory_database_accessible(),
    ]
    for name, ok, detail in checks:
        status = "OK" if ok else "MISSING"
        print(f"[{status:>7}] {name}: {detail}")
    return 0


def _print_worker_pass(pass_outcome: WorkerPassOutcome, *, not_due_count: int = 0) -> None:
    """Print one real worker pass's own outcomes -- shared by --once and continuous mode.

    ``not_due_count`` (WP-150) distinguishes two real, different
    "nothing happened" states that previously both printed the
    identical "no eligible tasks found" line: genuinely zero real
    `"created"` tasks, versus one or more real, scheduled tasks that
    simply haven't reached their own `scheduled_at` yet (WP-122). An
    unscheduled `"created"` task is always immediately eligible
    (WP-122's own unchanged design), so if `pass_outcome.attempted` is
    empty, any `"created"` records the caller separately counted here
    must all be scheduled-but-not-yet-due -- never a task the worker
    itself failed to notice.
    """
    attempted = pass_outcome.attempted
    if not attempted:
        if not_due_count > 0:
            print(
                f"worker: no tasks due right now ({not_due_count} 'created' task(s) "
                "scheduled for later)."
            )
        else:
            print("worker: no eligible ('created') tasks found.")
        return
    for outcome in attempted:
        if outcome.error is not None:
            print(f"worker: task {outcome.task_id} -- error: {outcome.error}")
        elif not outcome.claimed:
            print(f"worker: task {outcome.task_id} -- not claimed (status: {outcome.status})")
        else:
            print(f"worker: task {outcome.task_id} -- ran, status: {outcome.status}")


def _run_task_worker(args: argparse.Namespace) -> int:
    """Run the real background-task worker (WP-120) in the foreground until stopped.

    Foreground by default, no hidden daemonization -- mirrors
    ``_run_listen``'s own exact shape: a real, continuous loop this
    process blocks on, stopped by a real Ctrl+C (``KeyboardInterrupt``)
    or, deterministically, after ``--max-passes`` real passes (useful
    for scripted/automated runs, and the mechanism this module's own
    tests use -- never an unbounded loop inside an automated test).
    ``--once`` is the simplest, most deterministic mode: exactly one
    real pass, then exit, no sleep, no loop at all.
    """

    async def _one_pass() -> WorkerPassOutcome:
        return await run_pending_tasks_once(
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )

    def _pass_had_a_real_error(pass_outcome: WorkerPassOutcome) -> bool:
        return any(outcome.error is not None for outcome in pass_outcome.attempted)

    def _print_pass_with_scheduling_context(pass_outcome: WorkerPassOutcome) -> None:
        # WP-150: only pay for the extra, real memory.retrieve read when there is
        # genuinely nothing to distinguish -- an ordinary pass that attempted at
        # least one task never makes this second call.
        not_due_count = 0
        if not pass_outcome.attempted:
            list_outcome = authorize_and_list_tasks(
                status="created",
                physical_confirmation_available=args.physical_confirmation_available,
                remote_confirmation_available=args.remote_confirmation_available,
                chain_path=args.chain_path,
            )
            not_due_count = sum(
                1
                for record in list_outcome.records
                if record.identifier not in list_outcome.due_task_ids
            )
        _print_worker_pass(pass_outcome, not_due_count=not_due_count)

    if args.dry_run:
        # WP-139: a real, read-only inspection -- reuses authorize_and_list_tasks's own
        # already-computed due_task_ids (WP-125) directly; never calls
        # authorize_and_run_task/run_pending_tasks_once, so nothing is ever claimed or
        # run, no matter what --once/--max-passes/--poll-interval-seconds were given.
        list_outcome = authorize_and_list_tasks(
            status="created",
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        if not list_outcome.records:
            print("worker: no eligible ('created') tasks found.")
            return 0
        for record in list_outcome.records:
            data = record.value.value
            goal = data.get("goal") if isinstance(data, dict) else None
            due = record.identifier in list_outcome.due_task_ids
            print(f"worker: task {record.identifier} -- goal={goal!r}, due={due}")
        return 0

    if args.once:
        pass_outcome = asyncio.run(_one_pass())
        _print_pass_with_scheduling_context(pass_outcome)
        # WP-132: a non-zero exit lets a script/cron job/systemd unit detect a real
        # per-task error without parsing printed text -- the worker's own tolerant,
        # never-abort-the-pass behavior (module docstring) is completely unchanged;
        # this only changes what this CLI invocation reports to the OS afterward.
        return 1 if _pass_had_a_real_error(pass_outcome) else 0

    print(
        "Running the background task worker -- polling every "
        f"{args.poll_interval_seconds}s. Press Ctrl+C to stop."
    )
    passes_run = 0
    any_error = False
    try:
        while args.max_passes is None or passes_run < args.max_passes:
            pass_outcome = asyncio.run(_one_pass())
            _print_pass_with_scheduling_context(pass_outcome)
            any_error = any_error or _pass_had_a_real_error(pass_outcome)
            passes_run += 1
            if args.max_passes is not None and passes_run >= args.max_passes:
                break
            time.sleep(args.poll_interval_seconds)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 1 if any_error else 0


def _run_listen(chain_path: Path, *, verbose: bool) -> int:
    """Run the voice loop in the foreground until interrupted.

    Constructs the one real ``Gtk4PhysicalConfirmationAdapter`` this
    project builds -- see this module's own docstring for why that
    construction has to happen here, in ``cli``, rather than in
    ``kernel``. Every other port ``run_voice_loop`` needs defaults to
    its own real adapter internally; only this one doesn't, so this is
    the only port this function passes explicitly.
    """
    _configure_logging(verbose=verbose)
    print("Listening -- say the wake phrase, then a command. Press Ctrl+C to stop.")

    try:
        asyncio.run(
            run_voice_loop(
                chain_path=chain_path,
                physical_confirmation=Gtk4PhysicalConfirmationAdapter(),
            )
        )
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


def _email_port_from_ui_args(args: argparse.Namespace) -> ImapEmailAdapter | None:
    """Construct a real ImapEmailAdapter for `jarvis ui`'s own optional email flags (WP-114).

    `None` unless all four connection flags were supplied together --
    mirrors `_run_email_subcommand`'s own real construction exactly,
    just optional here since email is not required to run `jarvis ui`
    at all.
    """
    if (
        args.email_imap_host is None
        or args.email_smtp_host is None
        or args.email_username is None
        or args.email_password_reference is None
    ):
        return None
    return ImapEmailAdapter(
        args.email_imap_host,
        args.email_username,
        SecretServiceAdapter(),
        args.email_password_reference,
        smtp_host=args.email_smtp_host,
    )


def _calendar_port_from_ui_args(args: argparse.Namespace) -> CalDavCalendarAdapter | None:
    """Construct a real CalDavCalendarAdapter for `jarvis ui`'s own optional calendar flags.

    See `_email_port_from_ui_args`'s own identical reasoning (WP-114).
    """
    if (
        args.calendar_caldav_url is None
        or args.calendar_username is None
        or args.calendar_password_reference is None
    ):
        return None
    return CalDavCalendarAdapter(
        args.calendar_caldav_url,
        args.calendar_username,
        SecretServiceAdapter(),
        args.calendar_password_reference,
    )


def _run_ui(args: argparse.Namespace) -> int:
    """Serve the JARVIS UI foundation (WP-108) in the foreground until interrupted.

    Mirrors :func:`_run_listen`'s own "continuous, foreground process,
    Ctrl+C to stop" shape exactly, including no ``--physical-``/
    ``--remote-confirmation-available`` per-call reinterpretation --
    unlike ``listen``, this command *does* take those two flags, since
    ``jarvis.cli.ui_server.UiServerConfig`` applies them uniformly to
    every request for the server's own lifetime (see that module's own
    docstring for why this is a real, deliberate choice, not an
    oversight).

    WP-114: ``email_port``/``calendar_port`` are real, optional ports
    constructed here (``cli`` is the one layer permitted to construct
    concrete adapters) -- ``None`` unless the operator supplied the
    matching connection flags, exactly mirroring
    ``email_port``/``calendar_port``'s own established "no implicit
    default" precedent everywhere else in this codebase.
    """
    config = UiServerConfig(
        chain_path=args.chain_path,
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        database_path=args.database_path,
        email_port=_email_port_from_ui_args(args),
        calendar_port=_calendar_port_from_ui_args(args),
    )
    server = create_server(args.port, config)
    bound_port = server.server_address[1]
    print(f"Serving JARVIS UI at http://127.0.0.1:{bound_port} -- press Ctrl+C to stop.")
    try:
        run_ui_server(server)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


def _run_memory_subcommand(  # noqa: PLR0911 -- one return per memory subcommand
    args: argparse.Namespace,
) -> tuple[Decision, str | None, tuple[MemoryRecord, ...] | None, int | None]:
    """Dispatch one ``memory`` subcommand, returning (decision, identifier, records, deleted_count).

    Split out from :func:`main` purely to keep its own branch count
    down -- one more subcommand family here would otherwise push
    ``main`` past ruff's ``PLR0912`` threshold. Each branch is a thin
    wrapper calling the matching ``jarvis.kernel.memory.authorize_and_*``
    function, exactly mirroring ``main``'s own ``ping``/``read``
    shape one level down.
    """
    if args.memory_command == "write":
        write_outcome = authorize_and_remember(
            args.text,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return write_outcome.decision, write_outcome.identifier, None, None
    if args.memory_command == "retrieve":
        recall_outcome = authorize_and_recall(
            args.query,
            limit=args.limit,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return recall_outcome.decision, None, recall_outcome.records, None
    if args.memory_command == "wipe":
        wipe_outcome = authorize_and_wipe_memory(
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return wipe_outcome.decision, None, None, wipe_outcome.deleted_count
    if args.memory_command == "forget":
        decision = authorize_and_forget(
            args.identifier,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return decision, None, None, None
    if args.memory_command == "backup":
        decision = authorize_and_backup_memory(
            args.destination,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return decision, None, None, None
    if args.memory_command == "restore":
        decision = authorize_and_restore_memory(
            args.source,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return decision, None, None, None

    decision = authorize_and_pin(
        args.identifier,
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        chain_path=args.chain_path,
    )
    return decision, None, None, None


def _run_communications_subcommand(args: argparse.Namespace) -> tuple[Decision, str | None]:
    """Dispatch ``send-email``/``create-calendar-event``, returning (decision, calendar_event_uid).

    Split out from :func:`main` for the identical reason
    :func:`_run_memory_subcommand` is: one more subcommand family
    inline in ``main`` would push it past ruff's ``PLR0912`` threshold.
    Both branches construct their own real adapter here (``cli`` is
    the one layer permitted to, mirroring ``_run_listen``'s own
    ``Gtk4PhysicalConfirmationAdapter`` construction) and wrap their
    kernel call in ``asyncio.run``, since both
    ``authorize_and_send_email``/``authorize_and_create_calendar_event``
    are ``async``.
    """
    if args.command == "send-email":
        email_port = ImapEmailAdapter(
            args.imap_host,
            args.username,
            SecretServiceAdapter(),
            args.password_reference,
            smtp_host=args.smtp_host,
        )
        decision = asyncio.run(
            authorize_and_send_email(
                tuple(args.to),
                args.subject,
                args.body,
                physical_confirmation_available=args.physical_confirmation_available,
                remote_confirmation_available=args.remote_confirmation_available,
                chain_path=args.chain_path,
                email_port=email_port,
            )
        )
        return decision, None

    calendar_port = CalDavCalendarAdapter(
        args.caldav_url,
        args.username,
        SecretServiceAdapter(),
        args.password_reference,
    )
    create_outcome = asyncio.run(
        authorize_and_create_calendar_event(
            args.summary,
            args.start,
            args.end,
            tuple(args.attendees),
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
            calendar_port=calendar_port,
        )
    )
    return create_outcome.decision, create_outcome.uid


def _run_email_subcommand(
    args: argparse.Namespace,
) -> tuple[Decision, tuple[Tainted[EmailSummary], ...] | None, Tainted[EmailMessage] | None]:
    """Dispatch ``email list``/``email read``, returning (decision, summaries, message).

    Split out from :func:`main` for the identical reason
    :func:`_run_communications_subcommand` is. Constructs a real
    ``ImapEmailAdapter`` here (``cli`` is the one layer permitted to,
    mirroring ``_run_communications_subcommand``'s own identical
    precedent) and wraps its kernel call in ``asyncio.run``, since both
    ``authorize_and_list_email``/``authorize_and_read_email`` are
    ``async``.
    """
    email_port = ImapEmailAdapter(
        args.imap_host,
        args.username,
        SecretServiceAdapter(),
        args.password_reference,
        smtp_host=args.smtp_host,
    )
    if args.email_command == "list":
        decision, summaries = asyncio.run(
            authorize_and_list_email(
                args.folder,
                args.limit,
                physical_confirmation_available=args.physical_confirmation_available,
                remote_confirmation_available=args.remote_confirmation_available,
                chain_path=args.chain_path,
                email_port=email_port,
            )
        )
        return decision, summaries, None

    decision, message = asyncio.run(
        authorize_and_read_email(
            args.message_id,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
            email_port=email_port,
        )
    )
    return decision, None, message


def _run_calendar_subcommand(
    args: argparse.Namespace,
) -> tuple[Decision, tuple[Tainted[CalendarEvent], ...] | None]:
    """Dispatch ``calendar list-events``, returning (decision, events).

    Split out from :func:`main` for the identical reason
    :func:`_run_email_subcommand` is. Constructs a real
    ``CalDavCalendarAdapter`` here, mirroring
    ``_run_communications_subcommand``'s own identical precedent for
    ``create-calendar-event``, and wraps its kernel call in
    ``asyncio.run``, since ``authorize_and_list_calendar_events`` is
    ``async``.
    """
    calendar_port = CalDavCalendarAdapter(
        args.caldav_url,
        args.username,
        SecretServiceAdapter(),
        args.password_reference,
    )
    return asyncio.run(
        authorize_and_list_calendar_events(
            args.start,
            args.end,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
            calendar_port=calendar_port,
        )
    )


def _run_reasoning_subcommand(args: argparse.Namespace) -> tuple[Decision, str | None]:
    """Dispatch ``code``/``draft``, returning (decision, result_label).

    Split out from :func:`main` for the identical reason
    :func:`_run_memory_subcommand`/:func:`_run_communications_subcommand`
    are. Both branches omit `dispatcher_factory`/`providers` entirely --
    the real, local-only default (`kernel/coding.py`'s
    `_local_only_dispatcher_factory`/`kernel/job_assistance.py`'s
    `_local_only_providers`) resolves automatically. Both kernel
    functions are `async`, so this wraps its own call in `asyncio.run`,
    the same shape `_run_communications_subcommand` already uses.
    """
    if args.command == "code":
        decision, coding_result = asyncio.run(
            authorize_and_run_coding_task(
                args.task,
                args.repo_path,
                physical_confirmation_available=args.physical_confirmation_available,
                remote_confirmation_available=args.remote_confirmation_available,
                chain_path=args.chain_path,
                max_climbs=args.max_climbs,
            )
        )
        outcome_label = coding_result.outcome.value if coding_result is not None else None
        return decision, outcome_label

    draft_outcome = asyncio.run(
        authorize_and_draft_document(
            args.task,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
            drafts_dir=args.drafts_dir,
        )
    )
    return draft_outcome.decision, (str(draft_outcome.path) if draft_outcome.path else None)


def _run_prepare_application_subcommand(
    args: argparse.Namespace,
) -> _CommandOutcome:
    """Dispatch ``prepare-application``, returning a full ``_CommandOutcome``.

    Split out from :func:`main` for the identical reason
    :func:`_run_reasoning_subcommand` is. Omits ``providers`` entirely,
    the same real, deliberate scope limit `_add_prepare_application_parsers`'s
    own docstring already states -- `authorize_and_prepare_application_folder`'s
    own real, local-only default (via `authorize_and_draft_document`)
    resolves automatically. `authorize_and_prepare_application_folder`
    is ``async``, so this wraps its own call in ``asyncio.run``, the
    same shape `_run_reasoning_subcommand` already uses.

    ``--record`` is a real, additive convenience only: a granted
    folder creation calls `authorize_and_record_job_application`
    completely unmodified (`status="drafted"`, `folder=` the real
    `<base_dir>/<month_label>` folder just created, derived from
    `outcome.cv_path`'s own parent's parent rather than re-deriving
    `month_dir` a second time). Without `--record` (the default),
    behavior is byte-for-byte identical to before this flag existed --
    no ledger call is ever made.
    """
    outcome = asyncio.run(
        authorize_and_prepare_application_folder(
            args.base_dir,
            args.month_label,
            args.cv_template,
            args.cover_letter_template,
            args.job_title,
            args.company,
            args.task_description,
            force=args.force,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
    )
    job_application_identifier: str | None = None
    if args.record and outcome.decision.granted and outcome.cv_path is not None:
        application_folder = outcome.cv_path.parent.parent
        record_outcome = authorize_and_record_job_application(
            args.company,
            args.job_title,
            status="drafted",
            folder=str(application_folder),
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        job_application_identifier = record_outcome.identifier
    return _CommandOutcome(
        outcome.decision,
        "prepare-application",
        application_cv_path=(str(outcome.cv_path) if outcome.cv_path else None),
        application_cover_letter_template_path=(
            str(outcome.cover_letter_template_path) if outcome.cover_letter_template_path else None
        ),
        application_job_application_identifier=job_application_identifier,
        application_draft_decision=outcome.draft_decision,
        application_body_path=(str(outcome.body_path) if outcome.body_path else None),
    )


def _run_job_application_subcommand(
    args: argparse.Namespace,
) -> tuple[Decision, tuple[MemoryRecord, ...] | None]:
    """Dispatch one ``job-application`` subcommand, returning (decision, records).

    Split out from :func:`_dispatch_command` for the identical reason
    :func:`_run_memory_subcommand` is. Both branches call straight
    into ``jarvis.kernel.job_application``, which itself reuses
    ``authorize_and_remember``/``authorize_and_recall`` unmodified --
    no new capability exists to dispatch to here.
    """
    if args.job_application_command == "record":
        write_outcome = authorize_and_record_job_application(
            args.company,
            args.role,
            status=args.status,
            folder=args.folder,
            notes=args.notes,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return write_outcome.decision, None

    list_outcome = authorize_and_list_job_applications(
        status=args.status,
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        chain_path=args.chain_path,
    )
    return list_outcome.decision, list_outcome.records


def _run_planning_subcommand(
    args: argparse.Namespace,
) -> tuple[Decision, tuple[PlanStepRecord, ...] | None]:
    """Dispatch ``plan run``, returning (decision, plan_step_records).

    Split out from :func:`main` for the identical reason
    :func:`_run_reasoning_subcommand` is. Omits ``provider`` entirely,
    the same real, deliberate scope limit ``_add_planning_parsers``'s
    own docstring already states -- ``authorize_and_run_plan``'s own
    real, local-only default resolves automatically, now logging its
    own real, honest reliability warning (`kernel/planning.py`).
    `authorize_and_run_plan` is ``async``, so this wraps its own call
    in ``asyncio.run``, the same shape every other async kernel call
    in this module already uses.
    """
    decision, plan_result = asyncio.run(
        authorize_and_run_plan(
            args.goal,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
    )
    step_records = plan_result.step_records if plan_result is not None else None
    return decision, step_records


def _run_project_subcommand(args: argparse.Namespace) -> _CommandOutcome:
    """Dispatch ``project start``/``project status``, returning a full _CommandOutcome directly.

    Split out from :func:`_dispatch_command` for the identical reason
    :func:`_run_prepare_application_subcommand` is: this command's own
    payload (a state/reason/record-identifier triple, or a single
    looked-up record) doesn't fit the simpler ``(Decision, payload)``
    tuple shape most other ``_run_*_subcommand`` helpers return.
    ``authorize_and_start_project`` is ``async``, so ``start`` wraps
    its own call in ``asyncio.run``, the same shape
    ``_run_planning_subcommand`` already uses;
    ``authorize_and_get_project_status`` is sync, no wrapping needed,
    matching ``authorize_and_list_job_applications``'s own identical
    shape. Omits ``provider`` entirely on ``start``, the same real,
    deliberate scope limit ``_add_project_parsers``'s own docstring
    already states. A real ``PlanningError``/``PlanValidationError``
    from ``start`` is not caught here -- it propagates to ``main()``'s
    own existing broad except tuple, exactly like ``plan run`` already
    does; ``authorize_and_start_project`` has already durably recorded
    the real stuck reason to memory before it re-raises (see
    ``kernel/project.py``'s own module docstring).
    """
    if args.project_command == "start":
        start_outcome = asyncio.run(
            authorize_and_start_project(
                args.goal,
                physical_confirmation_available=args.physical_confirmation_available,
                remote_confirmation_available=args.remote_confirmation_available,
                chain_path=args.chain_path,
            )
        )
        return _CommandOutcome(
            start_outcome.decision,
            "project start",
            project_state=start_outcome.state,
            project_reason=start_outcome.reason,
            project_record_identifier=start_outcome.record_identifier,
        )

    status_outcome = authorize_and_get_project_status(
        args.goal,
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        chain_path=args.chain_path,
    )
    return _CommandOutcome(
        status_outcome.decision,
        "project status",
        project_status_record=status_outcome.record,
    )


def _run_task_subcommand(  # noqa: PLR0911 -- one return per task subcommand
    args: argparse.Namespace,
) -> _CommandOutcome:
    """Dispatch ``task create``/``run``/``status``/``list``/``cancel``/``retry``/``schedule``.

    Split out from :func:`_dispatch_command` for the identical reason
    :func:`_run_project_subcommand` is. ``authorize_and_run_task``/
    ``authorize_and_retry_task`` are ``async``, so ``run``/``retry``
    each wrap their own call in ``asyncio.run``;
    ``authorize_and_create_task``/``authorize_and_get_task``/
    ``authorize_and_list_tasks``/``authorize_and_cancel_task``/
    ``authorize_and_schedule_task`` (WP-122) are sync, no wrapping
    needed. Omits ``provider`` entirely on ``run``/``retry``, the same
    real, deliberate scope limit ``_add_task_parsers``'s own docstring
    already states. A real ``PlanningError``/``PlanValidationError``
    from ``run``/``retry`` is not caught here -- it propagates to
    ``main()``'s own existing broad except tuple, exactly like ``plan
    run``/``project start`` already do; ``authorize_and_run_task`` has
    already durably updated the task's own status before it re-raises,
    and ``retry`` delegates to that exact, unmodified function. A real
    ``ValueError`` from ``schedule`` (an invalid or naive timestamp,
    see ``authorize_and_schedule_task``) is likewise not caught here --
    it propagates to the same broad except tuple, which already
    catches ``ValueError`` for every other subcommand.
    """
    if args.task_command == "create":
        create_outcome = authorize_and_create_task(
            args.goal,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return _CommandOutcome(
            create_outcome.decision,
            "task create",
            task_id=create_outcome.task_id,
        )

    if args.task_command == "run":
        run_outcome = asyncio.run(
            authorize_and_run_task(
                args.task_id,
                args.goal,
                physical_confirmation_available=args.physical_confirmation_available,
                remote_confirmation_available=args.remote_confirmation_available,
                chain_path=args.chain_path,
            )
        )
        return _CommandOutcome(
            run_outcome.decision,
            "task run",
            task_status=run_outcome.status,
            task_reason=run_outcome.reason,
        )

    if args.task_command == "status":
        get_outcome = authorize_and_get_task(
            args.task_id,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return _CommandOutcome(
            get_outcome.decision,
            "task status",
            task_record=get_outcome.record,
            task_stale=get_outcome.stale,
            task_due=get_outcome.due,
        )

    if args.task_command == "cancel":
        cancel_outcome = authorize_and_cancel_task(
            args.task_id,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return _CommandOutcome(
            cancel_outcome.decision,
            "task cancel",
            task_cancelled=cancel_outcome.cancelled,
            task_reason=cancel_outcome.reason,
        )

    if args.task_command == "recover":
        recover_outcome = authorize_and_recover_task(
            args.task_id,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return _CommandOutcome(
            recover_outcome.decision,
            "task recover",
            task_recovered=recover_outcome.recovered,
            task_reason=recover_outcome.reason,
        )

    if args.task_command == "retry":
        retry_outcome = asyncio.run(
            authorize_and_retry_task(
                args.task_id,
                physical_confirmation_available=args.physical_confirmation_available,
                remote_confirmation_available=args.remote_confirmation_available,
                chain_path=args.chain_path,
            )
        )
        return _CommandOutcome(
            retry_outcome.decision,
            "task retry",
            task_retried=retry_outcome.retried,
            task_status=retry_outcome.status,
            task_reason=retry_outcome.reason,
        )

    if args.task_command == "schedule":
        schedule_outcome = authorize_and_schedule_task(
            args.task_id,
            args.scheduled_at,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return _CommandOutcome(
            schedule_outcome.decision,
            "task schedule",
            task_scheduled=schedule_outcome.scheduled,
            task_scheduled_at=schedule_outcome.scheduled_at,
            task_reason=schedule_outcome.reason,
        )

    list_outcome = authorize_and_list_tasks(
        status="created" if args.scheduled_only else args.status,
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        chain_path=args.chain_path,
    )
    if args.scheduled_only:
        list_outcome = filter_scheduled_tasks(list_outcome)
    return _CommandOutcome(
        list_outcome.decision,
        "task list",
        task_records=list_outcome.records,
        stale_task_ids=list_outcome.stale_task_ids,
        due_task_ids=list_outcome.due_task_ids,
    )


def _run_do_subcommand(args: argparse.Namespace) -> _CommandOutcome:
    """Dispatch `do "<text>"` -- WP-104's typed freeform command router.

    Split out from :func:`_dispatch_command` for the identical reason
    :func:`_run_task_subcommand` is. `authorize_and_route` is `async`,
    so this wraps its own call in `asyncio.run`, the same shape
    `plan run`/`project start`/`task run` already use. Omits
    `provider` entirely, the same real, deliberate scope limit those
    three already establish -- `authorize_and_route`'s own real,
    local-only reasoning-fallback default resolves automatically, with
    the same real, honest reliability warning `kernel/planning.py`'s
    own identical default logs.

    `outcome.decision` is `None` whenever `authorize_and_route` itself
    never attempted any downstream authorization (`RouteKind.UNKNOWN`,
    or a real, recognized capability with no wired executor) -- see
    `_CommandOutcome.decision`'s own widened type and `main()`'s own
    handling of that case.
    """
    route_outcome = asyncio.run(
        authorize_and_route(
            args.text,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
    )
    return _CommandOutcome(
        route_outcome.decision,
        "do",
        route_result=route_outcome.route,
        route_execution_result=route_outcome.execution_result,
        route_task_id=route_outcome.task_id,
    )


def _handle_from_args(args: argparse.Namespace) -> PageHandle:
    """Reconstruct a real PageHandle from a prior 'browser open' call's own printed fields."""
    return PageHandle(
        debug_port=args.debug_port,
        target_id=args.target_id,
        process_id=args.process_id,
        user_data_dir=args.user_data_dir,
    )


def _run_browser_subcommand(
    args: argparse.Namespace,
) -> _CommandOutcome:
    """Dispatch one ``browser`` subcommand, returning a full ``_CommandOutcome``.

    Every real ``kernel.browser`` composition function is ``async``,
    so each branch wraps its own call in ``asyncio.run``, the same
    shape ``_run_reasoning_subcommand``/``_run_prepare_application_subcommand``
    already use.
    """
    if args.browser_command == "open":
        decision, handle = asyncio.run(
            authorize_and_open_page(
                args.url,
                physical_confirmation_available=args.physical_confirmation_available,
                remote_confirmation_available=args.remote_confirmation_available,
                chain_path=args.chain_path,
            )
        )
        return _CommandOutcome(decision, "browser open", browser_page_handle=handle)

    if args.browser_command == "screenshot":
        decision, screenshot = asyncio.run(
            authorize_and_capture_screenshot(
                _handle_from_args(args),
                physical_confirmation_available=args.physical_confirmation_available,
                remote_confirmation_available=args.remote_confirmation_available,
                chain_path=args.chain_path,
            )
        )
        if screenshot is not None:
            args.output.write_bytes(screenshot.value)
        return _CommandOutcome(
            decision,
            "browser screenshot",
            browser_screenshot_path=(str(args.output) if screenshot is not None else None),
        )

    if args.browser_command == "inspect-dom":
        decision, html = asyncio.run(
            authorize_and_query_dom(
                _handle_from_args(args),
                args.selector,
                physical_confirmation_available=args.physical_confirmation_available,
                remote_confirmation_available=args.remote_confirmation_available,
                chain_path=args.chain_path,
            )
        )
        return _CommandOutcome(
            decision,
            "browser inspect-dom",
            browser_dom_html=(html.value if html is not None else None),
        )

    decision = asyncio.run(
        authorize_and_close_page(
            _handle_from_args(args),
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
    )
    return _CommandOutcome(decision, "browser close")


def _run_job_search_subcommand(args: argparse.Namespace) -> Decision:
    """Dispatch ``job-search``, returning its real Decision.

    `authorize_and_open_job_search` is synchronous (mirrors
    `authorize_and_open_brave_url`'s own shape, the real, ordinary
    Brave mechanism this capability reuses -- see
    `kernel/job_search.py`'s own module docstring), so no `asyncio.run`
    wrapping is needed here.
    """
    return authorize_and_open_job_search(
        JobSearchSite(args.site),
        args.keywords,
        args.location,
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        chain_path=args.chain_path,
    )


def _run_find_careers_page_subcommand(args: argparse.Namespace) -> Decision:
    """Dispatch ``find-careers-page``, returning its real Decision.

    `authorize_and_find_careers_page` is synchronous, the identical
    shape `_run_job_search_subcommand` already documents, for the same
    real reason.
    """
    return authorize_and_find_careers_page(
        args.company,
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        chain_path=args.chain_path,
    )


def _run_file_subcommand(args: argparse.Namespace) -> tuple[Decision, tuple[DirEntry, ...] | None]:
    """Dispatch ``list-dir``/``move-file``/``delete-file``, returning (decision, dir_entries).

    Split out from :func:`main` for the identical reason
    :func:`_run_reasoning_subcommand` is. Unlike the communications/
    reasoning helpers, all three `kernel/files.py` composition
    functions are plain sync calls (no I/O awaited), so this needs no
    `asyncio.run` wrapping. Only ``list-dir`` ever returns real
    entries; the other two return ``None`` there.
    """
    if args.command == "list-dir":
        outcome = authorize_and_list_dir(
            args.path,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        entries = (
            tuple(tainted.value for tainted in outcome.entries)
            if outcome.entries is not None
            else None
        )
        return outcome.decision, entries
    if args.command == "move-file":
        decision = authorize_and_move_file(
            args.source,
            args.destination,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return decision, None

    decision = authorize_and_delete_file(
        args.path,
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        chain_path=args.chain_path,
    )
    return decision, None


def _run_fs_search_subcommand(args: argparse.Namespace) -> _CommandOutcome:
    """Dispatch one ``fs`` subcommand (``find``/``search-content``/``recent``).

    Split out from :func:`_dispatch_command` for the identical reason
    :func:`_run_job_application_subcommand` is. All three real
    ``kernel/files.py`` composition functions are plain sync calls, no
    ``asyncio.run`` wrapping needed.
    """
    if args.fs_command == "find":
        find_outcome = authorize_and_find_files(
            args.pattern,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return _CommandOutcome(find_outcome.decision, "fs find", fs_paths=find_outcome.matches)

    if args.fs_command == "search-content":
        search_outcome = authorize_and_search_content(
            args.query,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return _CommandOutcome(
            search_outcome.decision,
            "fs search-content",
            fs_content_matches=search_outcome.matches,
            fs_search_capped=search_outcome.capped,
        )

    recent_outcome = authorize_and_list_recent_files(
        limit=args.limit,
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        chain_path=args.chain_path,
    )
    return _CommandOutcome(recent_outcome.decision, "fs recent", fs_paths=recent_outcome.files)


def _run_desktop_app_subcommand(args: argparse.Namespace) -> _CommandOutcome:
    """Dispatch open-brave-url/open-vscode-file/send-claude-text/send-chatgpt-text.

    Constructs a real `AtspiDesktopWindowAdapter()` directly for the
    two chat-app commands -- `kernel/desktop.py`'s own
    `authorize_and_send_text_to_chat_app` takes no default for this
    port (a C6 "no GLib in the core" restriction), and its own module
    docstring names `cli` as exactly the right, unrestricted place to
    supply the real one, mirroring `Gtk4PhysicalConfirmationAdapter`'s
    own identical precedent already in this module.
    """
    if args.command == "open-brave-url":
        decision = authorize_and_open_brave_url(
            args.url,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return _CommandOutcome(decision, args.command)
    if args.command == "open-vscode-file":
        decision = authorize_and_open_vscode_file(
            args.path,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return _CommandOutcome(decision, args.command)

    app = ChatApp.CLAUDE if args.command == "send-claude-text" else ChatApp.CHATGPT
    launch_command = _CLAUDE_APP_LAUNCH_COMMAND if app is ChatApp.CLAUDE else None
    decision = authorize_and_send_text_to_chat_app(
        app,
        args.text,
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        chain_path=args.chain_path,
        desktop_window=AtspiDesktopWindowAdapter(),
        launch_command=launch_command,
    )
    return _CommandOutcome(decision, args.command)


def _run_desktop_docker_subcommand(args: argparse.Namespace) -> _CommandOutcome:
    """Dispatch list-docker-containers/stop-docker-container.

    `docker.run_container`/`docker.build_image` are deliberately absent
    -- see `_add_desktop_parsers`'s own docstring.
    """
    if args.command == "list-docker-containers":
        outcome = authorize_and_list_docker_containers(
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return _CommandOutcome(outcome.decision, args.command, docker_containers=outcome.containers)

    decision = authorize_and_stop_docker_container(
        args.container,
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        chain_path=args.chain_path,
    )
    return _CommandOutcome(decision, args.command)


def _run_desktop_git_subcommand(args: argparse.Namespace) -> _CommandOutcome:
    """Dispatch git-status/git-create-branch/git-commit/git-push/git-force-push."""
    if args.command == "git-status":
        outcome = authorize_and_get_git_status(
            args.repo_dir,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return _CommandOutcome(outcome.decision, args.command, git_status_text=outcome.status)
    if args.command == "git-create-branch":
        decision = authorize_and_create_git_branch(
            args.repo_dir,
            args.branch_name,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return _CommandOutcome(decision, args.command)
    if args.command == "git-commit":
        decision = authorize_and_commit_git(
            args.repo_dir,
            args.message,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return _CommandOutcome(decision, args.command)
    if args.command == "git-push":
        decision = authorize_and_push_git(
            args.repo_dir,
            args.remote,
            args.branch,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return _CommandOutcome(decision, args.command)

    decision = authorize_and_force_push_git(
        args.repo_dir,
        args.remote,
        args.branch,
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        chain_path=args.chain_path,
    )
    return _CommandOutcome(decision, args.command)


_DESKTOP_APP_COMMANDS = (
    "open-brave-url",
    "open-vscode-file",
    "send-claude-text",
    "send-chatgpt-text",
)
_DESKTOP_DOCKER_COMMANDS = ("list-docker-containers", "stop-docker-container")
_DESKTOP_GIT_COMMANDS = (
    "git-status",
    "git-create-branch",
    "git-commit",
    "git-push",
    "git-force-push",
)
_ALL_DESKTOP_COMMANDS = _DESKTOP_APP_COMMANDS + _DESKTOP_DOCKER_COMMANDS + _DESKTOP_GIT_COMMANDS


def _run_desktop_subcommand(args: argparse.Namespace) -> _CommandOutcome:
    """Route any of the eleven wired desktop.*/docker.*/git.* commands to its own helper.

    Folds all three desktop-family helpers behind a single branch in
    :func:`_dispatch_command`, keeping that function's own
    return-statement count from growing by one per desktop command --
    the same "split out to keep the caller's own count down" pattern
    applied one level deeper.
    """
    if args.command in _DESKTOP_APP_COMMANDS:
        return _run_desktop_app_subcommand(args)
    if args.command in _DESKTOP_DOCKER_COMMANDS:
        return _run_desktop_docker_subcommand(args)
    return _run_desktop_git_subcommand(args)


@dataclass(frozen=True)
class _CommandOutcome:
    """Everything main() needs to print, gathered from one dispatched command.

    Split out from :func:`main` for the identical reason
    :func:`_run_memory_subcommand` is: keeping every possible optional
    print-payload as a separate local inside ``main`` itself would grow
    its own branch/statement count without bound as more subcommand
    families are added. All fields but ``decision``/``command_label``
    are ``None`` for most commands.

    ``decision`` is ``None`` for exactly one real case (WP-104's
    ``do``): a route that never caused any downstream authorization
    attempt at all (``RouteKind.UNKNOWN``, or a real, recognized
    capability with no wired executor) genuinely has no ``Decision``
    to report -- fabricating one would misrepresent what happened.
    Every other command still always supplies a real ``Decision``.
    """

    decision: Decision | None
    command_label: str
    content: Tainted[str] | None = None
    memory_identifier: str | None = None
    memory_records: tuple[MemoryRecord, ...] | None = None
    memory_deleted_count: int | None = None
    calendar_event_uid: str | None = None
    reasoning_result_label: str | None = None
    dir_entries: tuple[DirEntry, ...] | None = None
    docker_containers: tuple[str, ...] | None = None
    git_status_text: str | None = None
    audit_records: tuple[AuditRecord, ...] | None = None
    plan_step_records: tuple[PlanStepRecord, ...] | None = None
    email_summaries: tuple[Tainted[EmailSummary], ...] | None = None
    calendar_events: tuple[Tainted[CalendarEvent], ...] | None = None
    email_message: Tainted[EmailMessage] | None = None
    application_cv_path: str | None = None
    application_cover_letter_template_path: str | None = None
    application_draft_decision: Decision | None = None
    application_body_path: str | None = None
    application_job_application_identifier: str | None = None
    job_application_records: tuple[MemoryRecord, ...] | None = None
    browser_page_handle: PageHandle | None = None
    browser_screenshot_path: str | None = None
    browser_dom_html: str | None = None
    fs_paths: tuple[Path, ...] | None = None
    fs_content_matches: tuple[tuple[Path, int, str], ...] | None = None
    fs_search_capped: bool = False
    project_state: str | None = None
    project_reason: str | None = None
    project_record_identifier: str | None = None
    project_status_record: MemoryRecord | None = None
    task_id: str | None = None
    task_status: str | None = None
    task_reason: str | None = None
    task_record: MemoryRecord | None = None
    task_records: tuple[MemoryRecord, ...] | None = None
    task_stale: bool = False
    stale_task_ids: frozenset[str] = frozenset()
    task_due: bool = False
    due_task_ids: frozenset[str] = frozenset()
    task_cancelled: bool | None = None
    task_recovered: bool | None = None
    task_retried: bool | None = None
    task_scheduled: bool | None = None
    task_scheduled_at: str | None = None
    route_result: RouteResult | None = None
    route_execution_result: object | None = None
    route_task_id: str | None = None


def _run_basic_subcommand(
    args: argparse.Namespace,
) -> _CommandOutcome:
    """Dispatch ``ping``/``read``/``audit-history`` -- commands with no dedicated subcommand family.

    Split out from :func:`_dispatch_command` purely to keep its own
    return-statement count under ruff's `PLR0911` threshold as more
    subcommand families are added -- the file's own established
    "split out to keep the caller's own count down" pattern, applied
    one level deeper this time.
    """
    if args.command == "ping":
        decision = authorize_ping(
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return _CommandOutcome(decision, args.command)

    if args.command == "audit-history":
        history_outcome = authorize_and_view_audit_history(
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
            limit=args.limit,
            capability_id=args.capability_id,
        )
        return _CommandOutcome(
            history_outcome.decision, args.command, audit_records=history_outcome.records
        )

    outcome = authorize_and_read_file(
        args.path,
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        chain_path=args.chain_path,
    )
    return _CommandOutcome(outcome.decision, args.command, content=outcome.content)


def _dispatch_command(  # noqa: PLR0911, PLR0912 -- one return/branch per subcommand family, mirrors this module's flat dispatch shape
    args: argparse.Namespace,
) -> _CommandOutcome:
    """Route ``args.command`` to its matching kernel call, gathering everything to print.

    Split out from :func:`main` to keep `main` itself under ruff's
    `PLR0912` branch-count threshold as more subcommand families are
    added -- the same "split out to keep the caller's own count down"
    pattern `_run_memory_subcommand`/`_run_communications_subcommand`/
    `_run_reasoning_subcommand` already establish one level down.
    """
    if args.command in ("ping", "read", "audit-history"):
        return _run_basic_subcommand(args)
    if args.command == "memory":
        decision, memory_identifier, memory_records, memory_deleted_count = _run_memory_subcommand(
            args
        )
        return _CommandOutcome(
            decision,
            f"memory {args.memory_command}",
            memory_identifier=memory_identifier,
            memory_records=memory_records,
            memory_deleted_count=memory_deleted_count,
        )
    if args.command in ("send-email", "create-calendar-event"):
        decision, calendar_event_uid = _run_communications_subcommand(args)
        return _CommandOutcome(decision, args.command, calendar_event_uid=calendar_event_uid)
    if args.command in ("code", "draft"):
        decision, reasoning_result_label = _run_reasoning_subcommand(args)
        return _CommandOutcome(
            decision, args.command, reasoning_result_label=reasoning_result_label
        )
    if args.command == "plan":
        decision, plan_step_records = _run_planning_subcommand(args)
        return _CommandOutcome(
            decision, f"plan {args.plan_command}", plan_step_records=plan_step_records
        )
    if args.command == "project":
        return _run_project_subcommand(args)
    if args.command == "task":
        return _run_task_subcommand(args)
    if args.command == "do":
        return _run_do_subcommand(args)
    if args.command == "email":
        decision, email_summaries, email_message = _run_email_subcommand(args)
        return _CommandOutcome(
            decision,
            f"email {args.email_command}",
            email_summaries=email_summaries,
            email_message=email_message,
        )
    if args.command == "calendar":
        decision, calendar_events = _run_calendar_subcommand(args)
        return _CommandOutcome(
            decision, f"calendar {args.calendar_command}", calendar_events=calendar_events
        )
    if args.command == "browser":
        return _run_browser_subcommand(args)
    if args.command == "job-search":
        decision = _run_job_search_subcommand(args)
        return _CommandOutcome(decision, args.command)
    if args.command == "find-careers-page":
        decision = _run_find_careers_page_subcommand(args)
        return _CommandOutcome(decision, args.command)
    if args.command == "prepare-application":
        return _run_prepare_application_subcommand(args)
    if args.command == "job-application":
        decision, job_application_records = _run_job_application_subcommand(args)
        return _CommandOutcome(
            decision,
            f"job-application {args.job_application_command}",
            job_application_records=job_application_records,
        )
    if args.command in ("list-dir", "move-file", "delete-file"):
        decision, dir_entries = _run_file_subcommand(args)
        return _CommandOutcome(decision, args.command, dir_entries=dir_entries)
    if args.command == "fs":
        return _run_fs_search_subcommand(args)
    if args.command in _ALL_DESKTOP_COMMANDS:
        return _run_desktop_subcommand(args)

    decision = authorize_and_run_music_command(
        MUSIC_COMMAND_NAMES[args.command],
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        chain_path=args.chain_path,
    )
    return _CommandOutcome(decision, args.command)


def _print_project_outcome(outcome: _CommandOutcome) -> None:
    """Print a project start/status subcommand's own real payload.

    Split out from :func:`_print_outcome` purely to keep its own
    statement count under ruff's `PLR0915` threshold, the same reason
    `_print_job_application_table`/`_print_browser_outcome` already
    exist. Checking `outcome.command_label` for the "nothing found"
    message (rather than relying on field presence alone, the pattern
    every other branch here uses) is deliberate: unlike a list, a
    single, possibly-absent record can't otherwise be told apart from
    "this wasn't a project command at all" -- both leave
    `project_status_record` at its own default `None`.
    """
    if outcome.project_state is not None:
        print(f"state: {outcome.project_state}")
        if outcome.project_reason is not None:
            print(f"reason: {outcome.project_reason}")
        if outcome.project_record_identifier is not None:
            print(f"recorded: {outcome.project_record_identifier}")
    if outcome.project_status_record is not None:
        data = outcome.project_status_record.value.value
        if isinstance(data, dict):
            print(f"goal: {data.get('goal')}")
            # WP-109: the real, stored status is the canonical "failed" --
            # translated to "stuck" only here, for display, matching
            # `jarvis project status`'s own, unchanged printed-text
            # contract. A pre-WP-109 record already stored as "stuck"
            # passes through unchanged (not "failed", so untouched).
            stored_status = data.get("status")
            displayed_status = "stuck" if stored_status == "failed" else stored_status
            print(f"state: {displayed_status}")
            if data.get("reason") is not None:
                print(f"reason: {data.get('reason')}")
            print(f"updated_at: {data.get('updated_at')}")
        else:
            print(f"{outcome.project_status_record.identifier}: {data!r}")
    elif outcome.command_label == "project status":
        print("No project-goal record found for this goal.")


def _print_one_task_record(record: MemoryRecord, *, stale: bool = False, due: bool = False) -> None:
    """Print one real task record's own fields -- shared by `task status` and `task list`.

    ``stale`` is WP-116's own real, read-only staleness signal (see
    ``jarvis.kernel.tasks._is_stale_running``) -- never derived here,
    always computed by the kernel layer from the record's own
    ``updated_at`` against a real clock, then passed straight through.

    **WP-124**: also surfaces ``updated_at`` (when this record last
    genuinely changed -- WP-2's own "when it last changed" ask) and a
    compact rendering of WP-121's own durable ``attempts`` history
    (every concluded execution attempt, not just the current one) --
    both already stored on every real task record, neither previously
    printed anywhere.

    **WP-125**: ``due`` mirrors ``stale``'s own shape exactly (see
    ``jarvis.kernel.tasks.is_task_due``) -- printed only alongside
    ``scheduled_at`` itself, since due-ness is meaningless without a
    real schedule to be due (or not yet due) against.

    **WP-141**: also surfaces ``created_at`` (the one real, already-
    stored timestamp this function had never printed) -- investigated
    directly against WP-141's own "task inspect" ask and found this
    output already covers goal/status/reason/schedule/attempts/stale/
    due; a genuinely new, separate `jarvis task inspect` command would
    have been near-total duplication of this exact function, so the
    one real, missing field was added here instead.
    """
    data = record.value.value
    if not isinstance(data, dict):
        print(f"{record.identifier}: {data!r}")
        return
    print(f"{record.identifier}: goal={data.get('goal')!r} status={data.get('status')}")
    if data.get("reason") is not None:
        print(f"    reason: {data.get('reason')}")
    print(f"    created_at: {data.get('created_at')}")
    if data.get("scheduled_at") is not None:
        print(f"    scheduled_at: {data.get('scheduled_at')}")
        print(f"    due: {'true' if due else 'false'}")
    print(f"    updated_at: {data.get('updated_at')}")
    attempts = data.get("attempts")
    if isinstance(attempts, list) and attempts:
        print(f"    attempts ({len(attempts)}):")
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            print(
                f"      #{attempt.get('attempt')} {attempt.get('status')} "
                f"{attempt.get('started_at')} -> {attempt.get('ended_at')}"
            )
            if attempt.get("reason") is not None:
                print(f"          reason: {attempt.get('reason')}")
    if stale:
        print(
            "    warning: no status update in over "
            f"{int(STALE_RUNNING_THRESHOLD_SECONDS // 60)} minutes -- this task may have "
            "crashed or been interrupted; its status was never automatically changed"
        )


def _print_task_outcome(outcome: _CommandOutcome) -> None:  # noqa: PLR0912 -- one branch per optional field
    """Print a task create/run/status/list subcommand's own real payload.

    Split out from :func:`_print_outcome` for the identical reason
    `_print_project_outcome` already is.
    """
    if outcome.task_id is not None:
        print(f"task_id: {outcome.task_id}")
    if outcome.task_status is not None:
        print(f"status: {outcome.task_status}")
        if outcome.task_reason is not None:
            print(f"reason: {outcome.task_reason}")
    if outcome.task_cancelled is not None:
        print(f"cancelled: {'true' if outcome.task_cancelled else 'false'}")
        if not outcome.task_cancelled and outcome.task_reason is not None:
            print(f"reason: {outcome.task_reason}")
    if outcome.task_recovered is not None:
        print(f"recovered: {'true' if outcome.task_recovered else 'false'}")
        if outcome.task_reason is not None:
            print(f"reason: {outcome.task_reason}")
    if outcome.task_retried is not None:
        print(f"retried: {'true' if outcome.task_retried else 'false'}")
        # `status`/`reason` were already printed just above via the
        # `task_status` block whenever a real status exists (e.g. a
        # genuine retry attempt's own outcome) -- only print `reason`
        # here for the one real case that block skips entirely: no
        # task found at all, where `task_status` is `None`.
        if outcome.task_status is None and outcome.task_reason is not None:
            print(f"reason: {outcome.task_reason}")
    if outcome.task_scheduled is not None:
        print(f"scheduled: {'true' if outcome.task_scheduled else 'false'}")
        if outcome.task_scheduled:
            print(f"scheduled_at: {outcome.task_scheduled_at}")
        elif outcome.task_reason is not None:
            print(f"reason: {outcome.task_reason}")
    if outcome.task_record is not None:
        _print_one_task_record(outcome.task_record, stale=outcome.task_stale, due=outcome.task_due)
    elif outcome.command_label == "task status":
        print("No task found for this identifier.")
    if outcome.task_records is not None:
        for record in outcome.task_records:
            _print_one_task_record(
                record,
                stale=record.identifier in outcome.stale_task_ids,
                due=record.identifier in outcome.due_task_ids,
            )


def _print_do_outcome(outcome: _CommandOutcome) -> None:
    """Print a `do "<text>"` subcommand's own real route, plus whatever it caused.

    Split out from :func:`_print_outcome` for the identical reason
    `_print_project_outcome`/`_print_task_outcome` already are. Prints
    the real, structured `RouteResult` first -- what the router
    decided this request was, regardless of whether anything was
    authorized -- then, only if something was, the same
    `task_id`/record shape `task create` already prints via
    `_print_task_outcome`'s own sibling logic (not reused directly:
    a `COMPLEX_GOAL` route only ever produces a bare `task_id`, never
    a full task record, status, or reason).
    """
    route = outcome.route_result
    if route is None:
        return
    print(f"route: {route.kind.value} (source={route.source}, confidence={route.confidence})")
    if route.capability_id is not None:
        print(f"capability_id: {route.capability_id.value}")
    if route.goal is not None:
        print(f"goal: {route.goal}")
    if route.detail is not None:
        print(f"detail: {route.detail}")
    if outcome.decision is None:
        if route.kind == RouteKind.DETERMINISTIC_COMMAND:
            print(
                "This capability is recognized and registered, but is not wired for direct "
                "execution via 'do' yet -- use its own dedicated subcommand instead."
            )
        return
    if outcome.route_task_id is not None:
        print(f"task_id: {outcome.route_task_id}")
    if outcome.route_execution_result is not None:
        print(f"result: {outcome.route_execution_result!r}")


def _print_job_application_table(records: tuple[MemoryRecord, ...]) -> None:
    """Print job-application records as a real, readable table -- not a raw memory dump.

    Split out from :func:`_print_outcome` purely to keep its own
    statement count under ruff's `PLR0915` threshold, the same reason
    every other multi-line payload branch in this module has already
    been split out into its own function.
    """
    print(f"{'COMPANY':<20}  {'ROLE':<25}  {'DATE':<33}  {'STATUS':<14}  FOLDER")
    for job_record in records:
        data = job_record.value.value
        if not isinstance(data, dict):
            print(f"{job_record.identifier}: {data!r}")
            continue
        folder = data.get("folder") or "-"
        print(
            f"{data.get('company', '')!s:<20}  "
            f"{data.get('role', '')!s:<25}  "
            f"{data.get('date_applied', '')!s:<33}  "
            f"{data.get('status', '')!s:<14}  "
            f"{folder}"
        )


def _print_browser_outcome(outcome: _CommandOutcome) -> None:
    """Print a granted browser subcommand's own real payload -- a handle, a path, or DOM HTML.

    Split out from :func:`_print_outcome` purely to keep its own
    statement count under ruff's `PLR0915` threshold, the same reason
    `_print_job_application_table` already exists.
    """
    if outcome.browser_page_handle is not None:
        handle = outcome.browser_page_handle
        print(f"debug_port: {handle.debug_port}")
        print(f"target_id: {handle.target_id}")
        print(f"process_id: {handle.process_id}")
        print(f"user_data_dir: {handle.user_data_dir}")
    if outcome.browser_screenshot_path is not None:
        print(f"saved to: {outcome.browser_screenshot_path}")
    if outcome.browser_dom_html is not None:
        print(outcome.browser_dom_html)


def _print_fs_search_outcome(outcome: _CommandOutcome) -> None:
    """Print a granted fs find/search-content/recent subcommand's own real payload.

    Split out from :func:`_print_outcome` for the identical reason
    `_print_browser_outcome` already is.

    WP-163: a granted, zero-match result previously printed nothing at
    all here -- indistinguishable from a silent failure, the same real
    gap WP-144 already fixed for `jarvis memory retrieve`. Both real
    fields now print an honest message when empty.
    """
    if outcome.fs_paths is not None:
        if not outcome.fs_paths:
            print("No files found.")
        for path in outcome.fs_paths:
            print(str(path))
    if outcome.fs_content_matches is not None:
        if not outcome.fs_content_matches:
            print("No matching lines found.")
        for path, line_number, line in outcome.fs_content_matches:
            print(f"{path}:{line_number}: {line}")
        if outcome.fs_search_capped:
            print(
                "Warning: the file-count cap was reached -- this result may be incomplete.",
                file=sys.stderr,
            )


def _print_outcome(  # noqa: PLR0912, PLR0915 -- one branch per optional payload field
    outcome: _CommandOutcome,
) -> None:
    """Print every real payload a dispatched command produced, beyond the decision line.

    Split out from :func:`main` purely to keep its own branch count
    under ruff's `PLR0912` threshold as more optional payload fields
    are added to `_CommandOutcome` -- the file's own established
    "split out to keep the caller's own count down" pattern, applied
    to the print side this time rather than the dispatch side.
    """
    if outcome.content is not None:
        print(outcome.content.value)
    if outcome.memory_identifier is not None:
        print(f"identifier: {outcome.memory_identifier}")
    if outcome.memory_records is not None:
        if not outcome.memory_records:
            # WP-144: a granted recall with zero matches previously printed nothing at
            # all here -- indistinguishable from a real failure to a user watching the
            # terminal. Mirrors jarvis ui's own identical message
            # (_summarize_execution_result's MemoryRecallOutcome-with-no-records case).
            print("No matching memories found.")
        for record in outcome.memory_records:
            print(f"{record.identifier}: {record.value.value}")
    if outcome.memory_deleted_count is not None:
        print(f"deleted: {outcome.memory_deleted_count}")
    if outcome.job_application_records is not None:
        _print_job_application_table(outcome.job_application_records)
    _print_browser_outcome(outcome)
    _print_fs_search_outcome(outcome)
    _print_project_outcome(outcome)
    _print_task_outcome(outcome)
    _print_do_outcome(outcome)
    if outcome.calendar_event_uid is not None:
        print(f"uid: {outcome.calendar_event_uid}")
    if outcome.reasoning_result_label is not None:
        print(f"result: {outcome.reasoning_result_label}")
    if outcome.dir_entries is not None:
        for entry in outcome.dir_entries:
            print(f"{entry.name}{'/' if entry.is_dir else ''}")
    if outcome.docker_containers is not None:
        for container in outcome.docker_containers:
            print(container)
    if outcome.git_status_text is not None:
        print(outcome.git_status_text)
    if outcome.audit_records is not None:
        for audit_record in outcome.audit_records:
            record_decision = audit_record.decision
            status = "GRANTED" if record_decision.granted else "DENIED"
            print(
                f"{audit_record.sequence}: {record_decision.invocation.descriptor.id.value} "
                f"{status} (tier={record_decision.tier.name}, reasons={record_decision.reasons})"
            )
    if outcome.plan_step_records is not None:
        for step_record in outcome.plan_step_records:
            step_status = "GRANTED" if step_record.decision.granted else "DENIED"
            print(f"step: {step_record.step.capability_id.value} {step_status}")
    if outcome.email_summaries is not None:
        # WP-164: a granted, zero-message result previously printed nothing at all here --
        # the same gap WP-144/WP-163 already fixed for memory retrieve/fs find/search-content/
        # recent.
        if not outcome.email_summaries:
            print("No messages found.")
        for tainted_summary in outcome.email_summaries:
            summary = tainted_summary.value
            print(f"{summary.message_id}: {summary.sender} -- {summary.subject}")
    if outcome.calendar_events is not None:
        if not outcome.calendar_events:
            print("No events found.")
        for tainted_event in outcome.calendar_events:
            event = tainted_event.value
            print(f"{event.uid}: {event.summary} ({event.start} -- {event.end})")
    if outcome.email_message is not None:
        message = outcome.email_message.value
        print(f"From: {message.sender}")
        print(f"To: {', '.join(message.recipients)}")
        print(f"Subject: {message.subject}")
        print(f"Received: {message.received_at}")
        print()
        print(message.body)
    if outcome.application_cv_path is not None:
        print(f"CV copied to: {outcome.application_cv_path}")
        print(f"Cover letter template copied to: {outcome.application_cover_letter_template_path}")
        if outcome.application_draft_decision is not None:
            draft_status = "GRANTED" if outcome.application_draft_decision.granted else "DENIED"
            print(f"cover-letter body drafting: {draft_status}")
        if outcome.application_job_application_identifier is not None:
            print(f"job-application recorded: {outcome.application_job_application_identifier}")
        if outcome.application_body_path is not None:
            print(f"Cover letter body drafted to: {outcome.application_body_path}")
            print(
                r'Reminder: add one "\input{body.tex}" line to your own cover-letter '
                "template, once, by hand, wherever the body should appear -- this is "
                "never done automatically."
            )


def main(argv: Sequence[str] | None = None) -> int:  # noqa: PLR0911 -- one early return per continuous-mode command
    """Parse argv, authorize (and maybe run) the requested command, print the outcome.

    Args:
        argv: Arguments to parse, excluding the program name. Defaults
            to ``sys.argv[1:]`` (argparse's own default) when ``None``.

    Returns:
        ``0`` if the call was granted, ``1`` if denied, or if any of
        the errors below was raised. For ``listen``, ``0`` once
        stopped (via Ctrl+C) -- see :func:`_run_listen`.
    """
    args = _build_parser().parse_args(argv)
    if args.command == "listen":
        return _run_listen(args.chain_path, verbose=args.verbose)
    if args.command == "doctor":
        return _run_doctor()
    if args.command == "ui":
        return _run_ui(args)
    if args.command == "task" and args.task_command == "worker":
        return _run_task_worker(args)

    try:
        outcome = _dispatch_command(args)
    except (
        JarvisError,
        NoMediaPlayerRunningError,
        MediaPlayerCommandFailedError,
        PathOutsideAllowedScopeError,
        UnsupportedUrlSchemeError,
        SandboxUnavailableError,
        MemoryRecordNotFoundError,
        UnsupportedMemoryValueError,
        MemoryIntegrityViolationError,
        SecretNotFoundError,
        CalendarEventCreationError,
        EmailConnectionError,
        EmailMessageNotFoundError,
        BrowserLaunchFailedError,
        EditorLaunchFailedError,
        WindowNotFoundError,
        WindowActionFailedError,
        DockerCommandFailedError,
        GitCommandFailedError,
        PlanningError,
        PlanValidationError,
        ApplicationFolderAlreadyExistsError,
        ApplicationFolderOutsideBaseDirectoryError,
        OSError,
        UnicodeDecodeError,
        KeyError,
        ValueError,
        sqlite3.Error,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    decision = outcome.decision
    if decision is None:
        # WP-104's `do`: a route that never caused any downstream authorization attempt at
        # all (RouteKind.UNKNOWN, or a real capability with no wired executor) -- see
        # _CommandOutcome.decision's own widened-type docstring. Nothing was granted or
        # denied, so there is no real GRANTED/DENIED line to print; _print_outcome's own
        # _print_do_outcome prints the real route instead. A non-zero exit code reflects
        # that the request was not, in fact, fulfilled -- never silently reported as success.
        print(f"{outcome.command_label}: NOT_ROUTED")
        _print_outcome(outcome)
        return 1

    status = "GRANTED" if decision.granted else "DENIED"
    print(
        f"{outcome.command_label}: {status} (tier={decision.tier.name}, reasons={decision.reasons})"
    )
    _print_outcome(outcome)
    return 0 if decision.granted else 1
