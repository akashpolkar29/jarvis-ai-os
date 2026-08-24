"""The desktop window port: the seam between an authorized command and a real app window.

:class:`DesktopWindowPort` is the one abstract boundary between "some
real, running desktop application's window" and every UI-automation
capability M3 builds (Brave, VS Code, Terminal, and two consumer chat
desktop apps -- five of M3's eight target applications genuinely need
this; Spotify, Docker, Git do not). No vendor names appear in this
module, per ADR-0021 -- see ``docs/architecture/m3-desktop-control.md``
deliverable #1 for the full design reasoning and which real
applications are meant, and ADR-0045/ADR-0046 for the two capability-
*registration*-level restrictions this port itself does not enforce
(no response-scraping capability may be registered for either consumer
chat app; a Terminal capability's handle must originate from a
``SandboxPort``-launched process, never an arbitrary pre-existing
window).

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.desktop_window`` for the
concrete AT-SPI2-backed adapter that satisfies this port, and that
module's own docstring for why AT-SPI2 alone (not the Wayland portal's
RemoteDesktop/libei synthetic-input path the original design objective
named) is what WP-43's spike found to actually be usable here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.desktop import WindowHandle


class WindowNotFoundError(Exception):
    """Raised when no window for the requested ``app_id`` could be found or launched.

    Not a :class:`~jarvis.domain.errors.JarvisError` subclass: an
    adapter-level, real-world operational condition (the app isn't
    running, and either no launch command was given or launching it
    still produced no discoverable window in time), not a domain-level
    security/policy concern -- matching
    :class:`~jarvis.ports.media_player.NoMediaPlayerRunningError`'s
    own reasoning.
    """


class WindowActionFailedError(Exception):
    """Raised when a window was found but a real action against it failed.

    Covers ``focus``/``type_text`` failures: the accessible object no
    longer exists, doesn't implement the interface the action needs
    (e.g. no ``EditableText`` for ``type_text``), or the underlying
    call itself errored. Distinct from :class:`WindowNotFoundError` for
    the same reason
    :class:`~jarvis.ports.media_player.MediaPlayerCommandFailedError`
    is distinct from ``NoMediaPlayerRunningError``: "no window to act
    on" and "found a window but the action itself failed" are
    actionable differently.
    """


@runtime_checkable
class DesktopWindowPort(Protocol):
    """A real, running desktop application's window: findable, focusable, typeable-into."""

    def find_or_launch(
        self, app_id: str, launch_command: tuple[str, ...] | None = None
    ) -> WindowHandle:
        """Return a handle to a running window for ``app_id``, launching it if not found.

        Args:
            app_id: The application identifier to search for
                (adapter-specific matching, e.g. against a running
                process/application name).
            launch_command: If no matching window is found and this is
                given, run as a real subprocess before a second
                discovery attempt. If ``None`` and no window is found,
                :class:`WindowNotFoundError` is raised without
                attempting to launch anything.

        Raises:
            WindowNotFoundError: If no window is found and either no
                ``launch_command`` was given, or launching it still
                produced no discoverable window.
        """
        ...

    def focus(self, handle: WindowHandle) -> None:
        """Bring ``handle``'s window to the front and give it input focus.

        Raises:
            WindowActionFailedError: If ``handle`` no longer refers to
                a real window, or the underlying focus action failed.
        """
        ...

    def type_text(self, handle: WindowHandle, text: str) -> None:
        """Insert ``text`` into ``handle``'s window's currently-focused editable control.

        Callers must call :meth:`focus` first if they need this
        specific window actually focused -- this method does not
        implicitly focus anything itself.

        Raises:
            WindowActionFailedError: If ``handle`` no longer refers to
                a real window, or no editable text control could be
                found to receive ``text``.
        """
        ...

    def read_visible_text(self, handle: WindowHandle) -> str | None:
        """Best-effort: return ``handle``'s window's visible text, or ``None`` if unavailable.

        Not guaranteed -- depends entirely on whether the specific
        application exposes its content via AT-SPI2's ``Text``
        interface. Returns ``None`` rather than raising when the
        interface simply isn't implemented (a real, expected outcome
        for some apps, not an error); :class:`WindowActionFailedError`
        is still raised if ``handle`` itself no longer refers to a
        real window at all.

        Raises:
            WindowActionFailedError: If ``handle`` no longer refers to
                a real window.
        """
        ...
