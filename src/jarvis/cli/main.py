"""The CLI's argument parsing and result formatting -- no business logic.

:func:`main` parses argv into a subcommand (``ping``, ``play``,
``pause``, ``next``, ``previous``) and the confirmation/chain-path
flags every subcommand shares, calls the matching
``jarvis.kernel`` composition function, and formats the returned
``Decision`` for a terminal. It decides nothing about policy or
capabilities itself -- that is exactly the line this ring's own
docstring draws.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from jarvis.domain.errors import JarvisError
from jarvis.kernel.music import MusicCommand, authorize_and_run_music_command
from jarvis.kernel.ping import authorize_ping
from jarvis.ports.media_player import MediaPlayerCommandFailedError, NoMediaPlayerRunningError

if TYPE_CHECKING:
    from collections.abc import Sequence

_DEFAULT_CHAIN_PATH = Path("audit_chain.json")

_MUSIC_COMMANDS: dict[str, MusicCommand] = {
    "play": MusicCommand.PLAY,
    "pause": MusicCommand.PAUSE,
    "next": MusicCommand.NEXT,
    "previous": MusicCommand.PREVIOUS,
}


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

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse argv, authorize (and maybe run) the requested command, print the outcome.

    Args:
        argv: Arguments to parse, excluding the program name. Defaults
            to ``sys.argv[1:]`` (argparse's own default) when ``None``.

    Returns:
        ``0`` if the call was granted, ``1`` if denied, if a
        JarvisError was raised (e.g. a tampered audit chain), if no
        media player was reachable for a granted music command, or if
        a reachable player rejected the command it was sent.
    """
    args = _build_parser().parse_args(argv)

    try:
        if args.command == "ping":
            decision = authorize_ping(
                physical_confirmation_available=args.physical_confirmation_available,
                remote_confirmation_available=args.remote_confirmation_available,
                chain_path=args.chain_path,
            )
        else:
            decision = authorize_and_run_music_command(
                _MUSIC_COMMANDS[args.command],
                physical_confirmation_available=args.physical_confirmation_available,
                remote_confirmation_available=args.remote_confirmation_available,
                chain_path=args.chain_path,
            )
    except (JarvisError, NoMediaPlayerRunningError, MediaPlayerCommandFailedError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    status = "GRANTED" if decision.granted else "DENIED"
    print(f"{args.command}: {status} (tier={decision.tier.name}, reasons={decision.reasons})")
    return 0 if decision.granted else 1
