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
-- ``memory``'s subcommands follow that shape instead. Docker/Git
remain unwired for now, unrelated to this correction and out of this
pass's own named scope.

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
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from jarvis.adapters.memory import UnsupportedMemoryValueError
from jarvis.adapters.physical_confirmation import Gtk4PhysicalConfirmationAdapter
from jarvis.domain.errors import JarvisError
from jarvis.kernel.files import PathOutsideAllowedScopeError, authorize_and_read_file
from jarvis.kernel.memory import (
    authorize_and_forget,
    authorize_and_pin,
    authorize_and_recall,
    authorize_and_remember,
)
from jarvis.kernel.music import MUSIC_COMMAND_NAMES, authorize_and_run_music_command
from jarvis.kernel.ping import authorize_ping
from jarvis.kernel.voice_loop import run_voice_loop
from jarvis.ports.media_player import MediaPlayerCommandFailedError, NoMediaPlayerRunningError
from jarvis.ports.memory_write import MemoryRecordNotFoundError
from jarvis.ports.retrieval import MemoryIntegrityViolationError

if TYPE_CHECKING:
    from collections.abc import Sequence

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

    content: Tainted[str] | None = None
    memory_identifier: str | None = None
    memory_records: tuple[MemoryRecord, ...] | None = None
    command_label = args.command

    try:
        if args.command == "ping":
            decision = authorize_ping(
                physical_confirmation_available=args.physical_confirmation_available,
                remote_confirmation_available=args.remote_confirmation_available,
                chain_path=args.chain_path,
            )
        elif args.command == "read":
            outcome = authorize_and_read_file(
                args.path,
                physical_confirmation_available=args.physical_confirmation_available,
                remote_confirmation_available=args.remote_confirmation_available,
                chain_path=args.chain_path,
            )
            decision = outcome.decision
            content = outcome.content
        elif args.command == "memory":
            command_label = f"memory {args.memory_command}"
            decision, memory_identifier, memory_records = _run_memory_subcommand(args)
        else:
            decision = authorize_and_run_music_command(
                MUSIC_COMMAND_NAMES[args.command],
                physical_confirmation_available=args.physical_confirmation_available,
                remote_confirmation_available=args.remote_confirmation_available,
                chain_path=args.chain_path,
            )
    except (
        JarvisError,
        NoMediaPlayerRunningError,
        MediaPlayerCommandFailedError,
        PathOutsideAllowedScopeError,
        MemoryRecordNotFoundError,
        UnsupportedMemoryValueError,
        MemoryIntegrityViolationError,
        OSError,
        UnicodeDecodeError,
        KeyError,
        ValueError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    status = "GRANTED" if decision.granted else "DENIED"
    print(f"{command_label}: {status} (tier={decision.tier.name}, reasons={decision.reasons})")
    if content is not None:
        print(content.value)
    if memory_identifier is not None:
        print(f"identifier: {memory_identifier}")
    if memory_records is not None:
        for record in memory_records:
            print(f"{record.identifier}: {record.value.value}")
    return 0 if decision.granted else 1
