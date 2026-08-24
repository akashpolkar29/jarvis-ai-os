"""A pure, stdlib-only value type describing the outcome of running one real command.

:class:`CommandResult` was originally defined in
``jarvis.adapters.validation._command`` (M2, WP-33) as private, not-a-
port shared plumbing for that subpackage's five validator adapters.
M3's ``SandboxPort`` (ADR-0044) needs the exact same shape -- but a
``ports`` module can never import from ``adapters`` (C1 layered
architecture puts ``adapters`` above ``ports``; the dependency only
runs the other way). Rather than defining a second, duplicate shape
for the same concept (which ADR-0044 explicitly did not want), this
type is relocated here: pure data, stdlib only, so every layer
(``ports``, ``application``, ``adapters``) can depend on it. See
ADR-0044's own text for the real design reasoning; this module is the
mechanical fix that makes that reasoning legal under C1, not a new
decision of its own.

``jarvis.adapters.validation._command`` re-exports this type under its
original name so no M2 call site needed to change.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    """The real outcome of running one command: its exit code and captured output."""

    exit_code: int
    stdout: str
    stderr: str
