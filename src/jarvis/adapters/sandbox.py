"""Adapters implementing jarvis.ports.sandbox.SandboxPort.

:class:`BwrapSandboxAdapter` runs a command inside a real,
kernel-enforced sandbox via ``bwrap`` (bubblewrap), run as a real
subprocess. See ADR-0044 for the full design reasoning and the live
verification already performed on the real development machine during
WP-43/45: a real ``bwrap --unshare-all`` invocation, given only the
read-only system paths this adapter always binds, genuinely denies
outbound network and genuinely denies filesystem access outside
``bind_paths``, and a path explicitly bound is genuinely writable and
the write is genuinely visible on the host afterward.

Testable for real, like ``adapters/workspace.py``: ``bwrap`` is a
reliable CI dependency once installed via ``apt-get install
bubblewrap`` (added to CI alongside its existing PyGObject system-
dependency step), not a live service or piece of hardware that may or
may not be present. Two seams:

* :func:`_build_bwrap_argv` is pure (no I/O) and directly unit-tested:
  given a command and options, what real ``bwrap`` argv results.
* :class:`BwrapSandboxAdapter.run` actually executes that argv via a
  real subprocess by default; tests exercise both the pure argv-
  building logic directly and a handful of cases against a real
  ``bwrap`` process (matching ``LocalWorkspaceAdapter``'s own "test for
  real, no mocking" precedent), with the subprocess runner itself also
  injectable for the cases that don't need a real sandbox spun up.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from jarvis.domain.process import CommandResult

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    RunSubprocessFn = Callable[[tuple[str, ...]], CommandResult]

_BASE_ARGV: tuple[str, ...] = (
    "bwrap",
    "--ro-bind",
    "/usr",
    "/usr",
    "--ro-bind",
    "/etc",
    "/etc",
    "--symlink",
    "usr/bin",
    "/bin",
    "--symlink",
    "usr/lib",
    "/lib",
    "--symlink",
    "usr/lib64",
    "/lib64",
    "--tmpfs",
    "/tmp",  # noqa: S108 -- this is a sandbox-internal tmpfs mount point, not host /tmp usage
    "--proc",
    "/proc",
    "--dev",
    "/dev",
    "--unshare-all",
    "--die-with-parent",
)


def _build_bwrap_argv(
    command: tuple[str, ...], *, bind_paths: tuple[Path, ...], allow_network: bool
) -> tuple[str, ...]:
    """Build the real ``bwrap`` argv for ``command``. Pure, no I/O -- directly unit-tested.

    Real, verified base flags (ADR-0044): a read-only system view
    (``/usr``, ``/etc``, symlinked ``/bin``/``/lib``/``/lib64``), a
    fresh ``/tmp``/``/proc``/``/dev``, every namespace unshared
    (``--unshare-all``, including network), and ``--die-with-parent``
    so a sandboxed process never outlives the JARVIS process that
    launched it. ``bind_paths`` are each bound read-write at their own
    real path -- the only filesystem JARVIS explicitly grants access to
    beyond the read-only base.
    """
    argv = list(_BASE_ARGV)
    if allow_network:
        argv.append("--share-net")
    for path in bind_paths:
        text = str(path)
        argv.extend(["--bind", text, text])
    argv.append("--")
    argv.extend(command)
    return tuple(argv)


def _run_subprocess(argv: tuple[str, ...]) -> CommandResult:
    """Run ``argv`` as a real subprocess and capture its real outcome.

    The one real, untested-by-design piece of this module: it requires
    a real ``bwrap`` binary to actually be installed (confirmed present
    on the real development machine during WP-43;
    ``BwrapSandboxAdapter``'s own tests exercise this function for real
    rather than faking it, matching ``LocalWorkspaceAdapter``'s "git is
    a reliable CI dependency" precedent for ``bwrap``).
    """
    result = subprocess.run(  # noqa: S603 -- argv is built entirely from fixed flags plus typed
        # Path values (bind_paths) and a caller-supplied argv tuple, never shell text.
        argv,
        capture_output=True,
        text=True,
        check=False,
    )
    return CommandResult(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)


class BwrapSandboxAdapter:
    """Runs a command inside a real, kernel-enforced sandbox via a real ``bwrap`` subprocess."""

    def __init__(self, run_subprocess: RunSubprocessFn | None = None) -> None:
        """Store the function used to actually run the built argv. No I/O at construction time.

        Args:
            run_subprocess: Given a real argv, runs it and returns its
                outcome. Defaults to a real subprocess call. Overridable
                for tests that don't need a real sandbox spun up.
        """
        self._run_subprocess: RunSubprocessFn = run_subprocess or _run_subprocess

    def run(
        self,
        command: tuple[str, ...],
        *,
        bind_paths: tuple[Path, ...] = (),
        allow_network: bool = False,
    ) -> CommandResult:
        """Run ``command`` inside a real ``bwrap`` sandbox and return its real outcome."""
        argv = _build_bwrap_argv(command, bind_paths=bind_paths, allow_network=allow_network)
        return self._run_subprocess(argv)
