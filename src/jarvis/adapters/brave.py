"""Adapters implementing jarvis.ports.brave.BravePort.

:class:`BraveCliAdapter` launches or focuses Brave via a real
``brave-browser <url>`` subprocess call -- confirmed installed and
present on the real development machine during WP-43's spike
(``/usr/bin/brave-browser``, resolving to a real snap-packaged
``brave-browser``). No new protocol: Chromium-based browsers already
implement single-instance activation as a CLI convention -- passing a
URL to an already-running instance opens it in the existing window via
the browser's own IPC, with no ``DesktopWindowPort`` dependency needed
for this milestone's bounded scope (matches
``docs/architecture/m3-desktop-control.md``'s "Relationship to M5"
reasoning exactly: ``WorkspacePort``'s real ``git apply`` subprocess
call, ADR-0043, already established "shell out to a well-known CLI
with a fixed, non-shell-injectable argument list" as an accepted
pattern here).

**Never exercised for real during this unattended pass, deliberately**:
actually launching a real, visible browser window on the user's live
desktop is exactly the kind of uninvited real-environment side effect
this work package's hard-stop rule exists to avoid. The real launch
function is a small, injectable, untested-by-design seam (matching
``adapters/media_player.py``'s ``_send_method_call_over_dbus`` and
``adapters/desktop_window.py``'s ``_launch_subprocess``); every
automated test injects a fake in its place and exercises only this
adapter's own dispatch logic (which argv gets built, which error type
a launch failure becomes).
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from jarvis.ports.brave import BrowserLaunchFailedError

if TYPE_CHECKING:
    from collections.abc import Callable

    LaunchFn = Callable[[tuple[str, ...]], None]

_BRAVE_BINARY = "brave-browser"


def _launch_subprocess(argv: tuple[str, ...]) -> None:
    """Launch ``argv`` as a real, detached subprocess and return immediately.

    The one real, untested-by-design piece of this module (see the
    module docstring). ``argv`` is always exactly
    ``(_BRAVE_BINARY, url)`` -- never shell-interpreted, never built
    from caller-supplied text beyond the one ``url`` argument.
    """
    subprocess.Popen(  # noqa: S603 -- argv is a fixed binary name plus one typed url argument
        argv, start_new_session=True
    )


class BraveCliAdapter:
    """Launches or focuses Brave via a real ``brave-browser <url>`` subprocess call."""

    def __init__(self, launch: LaunchFn | None = None) -> None:
        """Store the function used to actually launch the subprocess. No I/O at construction time.

        Args:
            launch: Given a real argv, launches it. Defaults to a real
                subprocess launch. Overridable for tests, exactly as
                ``MprisMediaPlayerAdapter``'s ``send_method_call`` is.
        """
        self._launch: LaunchFn = launch or _launch_subprocess

    def open_url(self, url: str) -> None:
        """Launch or focus Brave, navigated to ``url``, via a real subprocess call.

        Raises:
            BrowserLaunchFailedError: If the underlying launch failed
                to even start (e.g. ``brave-browser`` is not installed).
        """
        try:
            self._launch((_BRAVE_BINARY, url))
        except OSError as exc:
            msg = f"Failed to launch {_BRAVE_BINARY}: {exc}"
            raise BrowserLaunchFailedError(msg) from exc
