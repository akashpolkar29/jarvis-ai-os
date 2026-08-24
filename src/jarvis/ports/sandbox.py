"""The sandbox port: real, contained command execution.

:class:`SandboxPort` is the one abstract boundary between "some
command JARVIS needs to run with real, kernel-enforced containment"
and the actual sandboxing technology used. See ADR-0044 for the full
design reasoning -- most importantly, that sandboxing is a
blast-radius-reduction measure only: it never changes which ``Tier`` a
capability requires (``domain/capability.py``'s tier calculus has no
knowledge this port exists at all).

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.sandbox`` for the
concrete ``bwrap``-backed adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.process import CommandResult


@runtime_checkable
class SandboxPort(Protocol):
    """A real, isolated environment a command can be run inside."""

    def run(
        self,
        command: tuple[str, ...],
        *,
        bind_paths: tuple[Path, ...] = (),
        allow_network: bool = False,
    ) -> CommandResult:
        """Run ``command`` inside a real, isolated sandbox and return its outcome.

        Args:
            command: The full argv to run, e.g. ``("bash",)``. Never
                shell-interpreted -- run exactly as given, matching
                every other subprocess-based adapter in this repo.
            bind_paths: Real host directories made read-write-visible
                inside the sandbox, at their own real path. No other
                host path is reachable by default (ADR-0044).
            allow_network: Whether the sandboxed command may reach the
                network. ``False`` (fully isolated) by default -- the
                one explicit escape hatch a future capability can opt
                into; none of M3's own capabilities set it.

        Returns:
            The command's real exit code, stdout, and stderr, the same
            shape ``jarvis.adapters.validation._command.run_command``
            already returns for unsandboxed commands.
        """
        ...
