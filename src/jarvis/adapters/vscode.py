"""Adapters implementing jarvis.ports.vscode.VsCodePort.

:class:`VsCodeCliAdapter` launches or focuses VS Code via a real
``code <path>`` subprocess call -- confirmed installed and present on
the real development machine during WP-43's spike (``/snap/bin/code``).
Same real, already-installed CLI-activation pattern
``adapters/brave.py`` uses for Brave: opening a path in an
already-running instance reuses the existing window via the editor's
own IPC, no LSP dependency for this milestone's bounded scope (see
``docs/architecture/m3-desktop-control.md``'s "Relationship to M5").

Not exercised for real during WP-43's own unattended implementation
pass, deliberately -- see ``adapters/brave.py``'s own docstring for the
identical reasoning (a real, visible editor window on the user's live
desktop was, at the time, exactly the uninvited real-environment side
effect that work package's hard-stop rule existed to avoid). **Since
live-verified for real**, in a later, explicitly-scoped pass that
authorized app-launching actions (overnight live-reality audit,
2026-08-25): a real ``open_file(".../CLAUDE.md")`` call completed
without exception, and a separate, independent AT-SPI2 check
afterward confirmed VS Code's window genuinely exists and is
discoverable -- see ``docs/threat-model/v0.md``'s "Overnight
live-reality audit" section. The real launch function remains a
small, injectable, untested-by-design-by-CI seam; automated tests
still inject a fake and exercise only this adapter's own dispatch
logic -- its correctness beyond that is now proven by the real, live
verification above, not merely asserted.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from jarvis.ports.vscode import EditorLaunchFailedError

if TYPE_CHECKING:
    from collections.abc import Callable

    LaunchFn = Callable[[tuple[str, ...]], None]

_CODE_BINARY = "code"


def _launch_subprocess(argv: tuple[str, ...]) -> None:
    """Launch ``argv`` as a real, detached subprocess and return immediately.

    The one real, untested-by-design piece of this module (see the
    module docstring). ``argv`` is always exactly
    ``(_CODE_BINARY, path)`` -- never shell-interpreted, never built
    from caller-supplied text beyond the one ``path`` argument.
    """
    subprocess.Popen(  # noqa: S603 -- argv is a fixed binary name plus one typed path argument
        argv, start_new_session=True
    )


class VsCodeCliAdapter:
    """Launches or focuses VS Code via a real ``code <path>`` subprocess call."""

    def __init__(self, launch: LaunchFn | None = None) -> None:
        """Store the function used to actually launch the subprocess. No I/O at construction time.

        Args:
            launch: Given a real argv, launches it. Defaults to a real
                subprocess launch. Overridable for tests, exactly as
                ``BraveCliAdapter``'s ``launch`` is.
        """
        self._launch: LaunchFn = launch or _launch_subprocess

    def open_file(self, path: str) -> None:
        """Launch or focus VS Code, opened to ``path``, via a real subprocess call.

        Raises:
            EditorLaunchFailedError: If the underlying launch failed to
                even start (e.g. ``code`` is not installed).
        """
        try:
            self._launch((_CODE_BINARY, path))
        except OSError as exc:
            msg = f"Failed to launch {_CODE_BINARY}: {exc}"
            raise EditorLaunchFailedError(msg) from exc
