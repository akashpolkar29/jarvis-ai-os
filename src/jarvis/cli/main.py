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
import logging
import sqlite3
import sys
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
from jarvis.domain.errors import JarvisError
from jarvis.kernel.coding import authorize_and_run_coding_task
from jarvis.kernel.communications import (
    authorize_and_create_calendar_event,
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
    authorize_and_list_dir,
    authorize_and_move_file,
    authorize_and_read_file,
)
from jarvis.kernel.job_assistance import authorize_and_draft_document
from jarvis.kernel.memory import (
    authorize_and_forget,
    authorize_and_pin,
    authorize_and_recall,
    authorize_and_remember,
)
from jarvis.kernel.music import MUSIC_COMMAND_NAMES, authorize_and_run_music_command
from jarvis.kernel.ping import authorize_ping
from jarvis.kernel.voice_loop import run_voice_loop
from jarvis.ports.brave import BrowserLaunchFailedError
from jarvis.ports.desktop_window import WindowActionFailedError, WindowNotFoundError
from jarvis.ports.docker import DockerCommandFailedError
from jarvis.ports.git import GitCommandFailedError
from jarvis.ports.media_player import MediaPlayerCommandFailedError, NoMediaPlayerRunningError
from jarvis.ports.memory_write import MemoryRecordNotFoundError
from jarvis.ports.retrieval import MemoryIntegrityViolationError
from jarvis.ports.secret import SecretNotFoundError
from jarvis.ports.vscode import EditorLaunchFailedError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from jarvis.domain.file_system import DirEntry
    from jarvis.domain.memory import MemoryRecord
    from jarvis.domain.policy import Decision
    from jarvis.domain.provenance import Tainted

_DEFAULT_CHAIN_PATH = Path("audit_chain.json")


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
    """Add the send-email/create-calendar-event subparsers, split out to keep _build_parser lean."""
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
            "provisioned out of band (ADR-0017/ADR-0042), not by this command."
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
            "provisioned out of band (ADR-0017/ADR-0042), not by this command."
        ),
    )
    _add_common_flags(create_event_parser)


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


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser: one subcommand per authorizable command."""
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="Authorize (and, if granted, run) one capability call.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ping_parser = subparsers.add_parser("ping", help='Authorize the no-op "ping" capability.')
    _add_common_flags(ping_parser)

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

    _add_communications_parsers(subparsers)
    _add_reasoning_parsers(subparsers)
    _add_file_parsers(subparsers)
    _add_desktop_parsers(subparsers)

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


def _run_memory_subcommand(
    args: argparse.Namespace,
) -> tuple[Decision, str | None, tuple[MemoryRecord, ...] | None]:
    """Dispatch one ``memory`` subcommand, returning (decision, identifier, records).

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
        return write_outcome.decision, write_outcome.identifier, None
    if args.memory_command == "retrieve":
        recall_outcome = authorize_and_recall(
            args.query,
            limit=args.limit,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return recall_outcome.decision, None, recall_outcome.records
    if args.memory_command == "forget":
        decision = authorize_and_forget(
            args.identifier,
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
        return decision, None, None

    decision = authorize_and_pin(
        args.identifier,
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        chain_path=args.chain_path,
    )
    return decision, None, None


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
    """

    decision: Decision
    command_label: str
    content: Tainted[str] | None = None
    memory_identifier: str | None = None
    memory_records: tuple[MemoryRecord, ...] | None = None
    calendar_event_uid: str | None = None
    reasoning_result_label: str | None = None
    dir_entries: tuple[DirEntry, ...] | None = None
    docker_containers: tuple[str, ...] | None = None
    git_status_text: str | None = None


def _run_basic_subcommand(args: argparse.Namespace) -> _CommandOutcome:
    """Dispatch ``ping``/``read``, the two commands with no dedicated subcommand family.

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

    outcome = authorize_and_read_file(
        args.path,
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        chain_path=args.chain_path,
    )
    return _CommandOutcome(outcome.decision, args.command, content=outcome.content)


def _dispatch_command(  # noqa: PLR0911 -- one return per subcommand family, mirrors this module's flat dispatch shape
    args: argparse.Namespace,
) -> _CommandOutcome:
    """Route ``args.command`` to its matching kernel call, gathering everything to print.

    Split out from :func:`main` to keep `main` itself under ruff's
    `PLR0912` branch-count threshold as more subcommand families are
    added -- the same "split out to keep the caller's own count down"
    pattern `_run_memory_subcommand`/`_run_communications_subcommand`/
    `_run_reasoning_subcommand` already establish one level down.
    """
    if args.command in ("ping", "read"):
        return _run_basic_subcommand(args)
    if args.command == "memory":
        decision, memory_identifier, memory_records = _run_memory_subcommand(args)
        return _CommandOutcome(
            decision,
            f"memory {args.memory_command}",
            memory_identifier=memory_identifier,
            memory_records=memory_records,
        )
    if args.command in ("send-email", "create-calendar-event"):
        decision, calendar_event_uid = _run_communications_subcommand(args)
        return _CommandOutcome(decision, args.command, calendar_event_uid=calendar_event_uid)
    if args.command in ("code", "draft"):
        decision, reasoning_result_label = _run_reasoning_subcommand(args)
        return _CommandOutcome(
            decision, args.command, reasoning_result_label=reasoning_result_label
        )
    if args.command in ("list-dir", "move-file", "delete-file"):
        decision, dir_entries = _run_file_subcommand(args)
        return _CommandOutcome(decision, args.command, dir_entries=dir_entries)
    if args.command in _ALL_DESKTOP_COMMANDS:
        return _run_desktop_subcommand(args)

    decision = authorize_and_run_music_command(
        MUSIC_COMMAND_NAMES[args.command],
        physical_confirmation_available=args.physical_confirmation_available,
        remote_confirmation_available=args.remote_confirmation_available,
        chain_path=args.chain_path,
    )
    return _CommandOutcome(decision, args.command)


def _print_outcome(outcome: _CommandOutcome) -> None:
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
        for record in outcome.memory_records:
            print(f"{record.identifier}: {record.value.value}")
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


def main(argv: Sequence[str] | None = None) -> int:
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

    try:
        outcome = _dispatch_command(args)
    except (
        JarvisError,
        NoMediaPlayerRunningError,
        MediaPlayerCommandFailedError,
        PathOutsideAllowedScopeError,
        MemoryRecordNotFoundError,
        UnsupportedMemoryValueError,
        MemoryIntegrityViolationError,
        SecretNotFoundError,
        CalendarEventCreationError,
        BrowserLaunchFailedError,
        EditorLaunchFailedError,
        WindowNotFoundError,
        WindowActionFailedError,
        DockerCommandFailedError,
        GitCommandFailedError,
        OSError,
        UnicodeDecodeError,
        KeyError,
        ValueError,
        sqlite3.Error,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    decision = outcome.decision
    status = "GRANTED" if decision.granted else "DENIED"
    print(
        f"{outcome.command_label}: {status} (tier={decision.tier.name}, reasons={decision.reasons})"
    )
    _print_outcome(outcome)
    return 0 if decision.granted else 1
