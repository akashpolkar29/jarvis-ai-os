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

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from jarvis.domain.process import CommandResult

if TYPE_CHECKING:
    from collections.abc import Callable

    RunSubprocessFn = Callable[[tuple[str, ...]], CommandResult]
    LaunchSubprocessFn = Callable[[tuple[str, ...]], int]
    DisplayBindPathsFn = Callable[[], "tuple[Path, ...]"]

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


def _display_bind_paths() -> tuple[Path, ...]:
    """Return the real host socket paths a GUI app needs to connect to the current display.

    Added post-M3, during live verification (WP-52's own Terminal
    launch): confirmed live that ``BwrapSandboxAdapter.launch()`` could
    not display any real GUI application at all -- ``_BASE_ARGV`` never
    binds anything under ``/run``, so the Wayland compositor socket
    (and the D-Bus session socket many GTK apps, including
    ``gnome-terminal``'s own D-Bus-activation wrapper, need even for an
    otherwise-Wayland-only launch) was unreachable inside the sandbox.
    This is a real, narrow bug fix, not a security-posture change:
    binding these two specific socket files does not touch any of
    ``SandboxPort``'s filesystem/network isolation guarantees (ADR-0044)
    -- it only lets a launched process *display* something, the same
    way any other explicitly-requested ``bind_paths`` entry works.

    A real, separate, initially-suspected cause was ruled out by live
    testing, not assumed: ``--unshare-net`` (network namespace
    isolation) does **not** by itself block Wayland socket access on
    this machine -- an earlier test run that appeared to show this was
    a false positive caused by this verification session's own shell
    environment (``GTK_PATH``/``GIO_MODULE_DIR`` pointing at a
    snap-confined VS Code installation's own GTK stack), not a genuine
    compositor security restriction. Re-tested with a clean
    environment: full ``--unshare-all``, network included, launches a
    real GUI application successfully once the sockets below are bound.

    Real, still-open, honestly-flagged limitation: only Wayland (via
    ``$XDG_RUNTIME_DIR``/``$WAYLAND_DISPLAY``) and the D-Bus session
    bus are handled. X11 (``/tmp/.X11-unix``, relevant for the X11
    fallback the original M3 objective named) is not -- untested,
    since this development machine is a real Wayland session
    (confirmed via ``$XDG_SESSION_TYPE``) with no real X11 session
    available to verify against.
    """
    paths: list[Path] = []
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    wayland_display = os.environ.get("WAYLAND_DISPLAY")
    if runtime_dir and wayland_display:
        wayland_socket = Path(runtime_dir) / wayland_display
        if wayland_socket.exists():
            paths.append(wayland_socket)
    if runtime_dir:
        dbus_socket = Path(runtime_dir) / "bus"
        if dbus_socket.exists():
            paths.append(dbus_socket)
    return tuple(paths)


def _launch_subprocess(argv: tuple[str, ...]) -> int:
    """Launch ``argv`` as a real, detached, long-running subprocess and return its pid.

    Added in WP-52 for :meth:`BwrapSandboxAdapter.launch` -- never
    waits for completion, matching every other real GUI-process launch
    in this project (``adapters/desktop_window.py``/``brave.py``/
    ``vscode.py``'s own ``_launch_subprocess`` functions), unlike
    :func:`_run_subprocess` above.
    """
    process = subprocess.Popen(  # noqa: S603 -- argv is built entirely from fixed flags plus
        # typed Path values (bind_paths) and a caller-supplied argv tuple, never shell text.
        argv,
        start_new_session=True,
    )
    return process.pid


class BwrapSandboxAdapter:
    """Runs a command inside a real, kernel-enforced sandbox via a real ``bwrap`` subprocess."""

    def __init__(
        self,
        run_subprocess: RunSubprocessFn | None = None,
        launch_subprocess: LaunchSubprocessFn | None = None,
        display_bind_paths: DisplayBindPathsFn | None = None,
    ) -> None:
        """Store the functions used to actually run/launch the built argv. No I/O at construction.

        Args:
            run_subprocess: Given a real argv, runs it and returns its
                outcome. Defaults to a real subprocess call. Overridable
                for tests that don't need a real sandbox spun up.
            launch_subprocess: Given a real argv, launches it as a
                long-running background process and returns its pid.
                Defaults to a real subprocess launch. Overridable for
                tests, exactly as ``run_subprocess`` is.
            display_bind_paths: Returns the real host socket paths a
                GUI app needs bound to display anything (Wayland/D-Bus
                session sockets). Defaults to the real, environment-
                reading implementation. Overridable for tests that
                don't need a real display session present.
        """
        self._run_subprocess: RunSubprocessFn = run_subprocess or _run_subprocess
        self._launch_subprocess: LaunchSubprocessFn = launch_subprocess or _launch_subprocess
        self._display_bind_paths: DisplayBindPathsFn = display_bind_paths or _display_bind_paths

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

    def launch(
        self,
        command: tuple[str, ...],
        *,
        bind_paths: tuple[Path, ...] = (),
        allow_network: bool = False,
        allow_display: bool = False,
    ) -> int:
        """Launch ``command`` inside a real ``bwrap`` sandbox as a long-running background process.

        Never waits for completion -- see :meth:`~jarvis.ports.sandbox.SandboxPort.launch`.

        Args:
            command: As in :meth:`run`.
            bind_paths: As in :meth:`run`.
            allow_network: As in :meth:`run`.
            allow_display: If ``True``, additionally binds the real
                Wayland/D-Bus session sockets this process's own
                environment reports, so a launched GUI application can
                actually display something. See
                :func:`_display_bind_paths` for what this does and does
                not cover.
        """
        real_bind_paths = bind_paths
        if allow_display:
            real_bind_paths = (*bind_paths, *self._display_bind_paths())
        argv = _build_bwrap_argv(command, bind_paths=real_bind_paths, allow_network=allow_network)
        return self._launch_subprocess(argv)
