"""The CLI's argument parsing and result formatting -- no business logic.

:func:`main` parses argv into the flags :func:`~jarvis.kernel.ping.authorize_ping`
needs, calls it, and formats the returned ``Decision`` for a terminal.
It decides nothing about policy or capabilities itself -- that is
exactly the line this ring's own docstring draws.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from jarvis.domain.errors import JarvisError
from jarvis.kernel.ping import authorize_ping

if TYPE_CHECKING:
    from collections.abc import Sequence

_DEFAULT_CHAIN_PATH = Path("audit_chain.json")


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the "ping" authorization command."""
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description='Authorize one call to the hardcoded "ping" capability.',
    )
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse argv, authorize one "ping" call, print the outcome, return an exit code.

    Args:
        argv: Arguments to parse, excluding the program name. Defaults
            to ``sys.argv[1:]`` (argparse's own default) when ``None``.

    Returns:
        ``0`` if the call was granted, ``1`` if denied or if a
        JarvisError was raised (e.g. a tampered audit chain).
    """
    args = _build_parser().parse_args(argv)

    try:
        decision = authorize_ping(
            physical_confirmation_available=args.physical_confirmation_available,
            remote_confirmation_available=args.remote_confirmation_available,
            chain_path=args.chain_path,
        )
    except JarvisError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    status = "GRANTED" if decision.granted else "DENIED"
    print(f"ping: {status} (tier={decision.tier.name}, reasons={decision.reasons})")
    return 0 if decision.granted else 1
