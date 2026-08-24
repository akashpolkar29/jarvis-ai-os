"""The Brave port: the seam between an authorized command and the real browser.

:class:`BravePort` is the one abstract boundary between "launch or
focus the real Brave browser, navigated to a URL" and the capability
that authorizes it. Ordinary control only, per
``docs/architecture/m3-desktop-control.md``'s "Relationship to M5"
section: this port never inspects page content or executes JavaScript
-- that is M5's own, deliberately separate, CDP-driven scope, not
touched by M3 at all.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.brave`` for the concrete
CLI-backed adapter that satisfies this port.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class BrowserLaunchFailedError(Exception):
    """Raised when launching or focusing the browser with a URL fails to even start.

    Not a :class:`~jarvis.domain.errors.JarvisError` subclass: an
    adapter-level, real-world operational condition (e.g. the
    ``brave-browser`` binary is not installed), not a domain-level
    security/policy concern -- matching
    :class:`~jarvis.ports.media_player.NoMediaPlayerRunningError`'s
    own reasoning.
    """


@runtime_checkable
class BravePort(Protocol):
    """The real, installed browser: launchable or focusable, navigated to one URL."""

    def open_url(self, url: str) -> None:
        """Launch or focus the browser, navigated to ``url``.

        Args:
            url: The URL to navigate to. Not validated or parsed here
                -- passed through to the real browser exactly as given.

        Raises:
            BrowserLaunchFailedError: If the underlying launch failed
                to even start.
        """
        ...
