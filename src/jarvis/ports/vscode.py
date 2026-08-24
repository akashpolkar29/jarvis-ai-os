"""The VS Code port: the seam between an authorized command and the real editor.

:class:`VsCodePort` is the one abstract boundary between "launch or
focus the real VS Code editor, opened to a file" and the capability
that authorizes it. Ordinary control only, per
``docs/architecture/m3-desktop-control.md``'s "Relationship to M5"
section: this port never talks to a language server or drives coding
capabilities -- that is M5's own, deliberately separate, LSP-driven
scope, not touched by M3 at all.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.vscode`` for the
concrete CLI-backed adapter that satisfies this port.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class EditorLaunchFailedError(Exception):
    """Raised when launching or focusing the editor with a file fails to even start.

    Not a :class:`~jarvis.domain.errors.JarvisError` subclass: an
    adapter-level, real-world operational condition (e.g. the ``code``
    binary is not installed), not a domain-level security/policy
    concern -- matching
    :class:`~jarvis.ports.brave.BrowserLaunchFailedError`'s own
    reasoning.
    """


@runtime_checkable
class VsCodePort(Protocol):
    """The real, installed editor: launchable or focusable, opened to one file."""

    def open_file(self, path: str) -> None:
        """Launch or focus the editor, opened to ``path``.

        Args:
            path: The file path to open. Not validated or resolved
                here -- passed through to the real editor exactly as
                given.

        Raises:
            EditorLaunchFailedError: If the underlying launch failed to
                even start.
        """
        ...
