"""The browser-automation port: the seam between an authorized command and a real, CDP-driven page.

:class:`BrowserAutomationPort` is M5's *deep*, CDP-driven counterpart
to M3's *shallow* :class:`~jarvis.ports.brave.BravePort`
(``docs/architecture/m3-desktop-control.md``'s own "Relationship to
M5" section drew that split; this port is the real thing that section
deferred). Real, working name, not a fixed decision the user has
confirmed: ``docs/architecture/m5-scoping-notes.md``'s own Part 2
research left the choice between a protocol-named port (mirroring how
``DesktopWindowPort``'s own docstring already names AT-SPI2 directly)
and a fully generic one genuinely open --
``docs/architecture/m5-browser-coding.md``'s own "Real gaps" section
names this exact question and picks this name as a working placeholder
for this drafting/implementation pass, not a confirmed choice.

No vendor names appear in this module, per ADR-0021 -- "CDP" and
"Chrome DevTools Protocol" are the open protocol standard's own name,
not a vendor, the same reasoning ``DesktopWindowPort``'s own docstring
already applies to naming AT-SPI2 directly.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.browser_automation`` for
the concrete CDP-backed adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.browser import PageHandle


class BrowserLaunchFailedError(Exception):
    """Raised when launching a real, CDP-controlled browser page fails to even start.

    Not a :class:`~jarvis.domain.errors.JarvisError` subclass: an
    adapter-level, real-world operational condition (e.g. the
    ``brave-browser`` binary is not installed, or the real DevTools
    endpoint never came up in time), not a domain-level security/policy
    concern -- matching
    :class:`~jarvis.ports.brave.BrowserLaunchFailedError`'s own
    reasoning exactly (a distinct type, not a reuse of that one: this
    port's own real failure mode -- a CDP endpoint that never becomes
    reachable -- is genuinely different from a plain subprocess launch
    failure).
    """


class BrowserActionFailedError(Exception):
    """Raised when a real page was reached but a real CDP action against it failed.

    Covers ``capture_screenshot``/``query_dom`` failures against a
    ``PageHandle`` whose underlying browser process or page no longer
    exists, or whose real CDP call itself errored -- matching
    :class:`~jarvis.ports.desktop_window.WindowActionFailedError`'s
    own "found the thing, but the action on it failed" distinction from
    :class:`BrowserLaunchFailedError`'s "never reached it at all."
    """


@runtime_checkable
class BrowserAutomationPort(Protocol):
    """A real, CDP-controlled browser page: openable, screenshottable, DOM-queryable."""

    async def open_page(self, url: str) -> PageHandle:
        """Launch a real, dedicated, CDP-controlled browser instance, navigated to ``url``.

        A dedicated instance, not the user's own already-open Brave
        window (M3's ``BravePort.open_url`` owns that shallow,
        ordinary-control case unchanged) -- real, deliberate isolation
        from the user's live browsing session, matching every
        real, publicly-documented CDP-automation tool's own established
        practice of launching a fresh, isolated profile rather than
        attaching to an arbitrary already-running instance it did not
        launch itself.

        Args:
            url: The URL to navigate the new page to.

        Returns:
            A real, reconnectable :class:`~jarvis.domain.browser.PageHandle`
            for the newly created page -- valid for as long as the
            underlying browser subprocess keeps running (see
            :meth:`close`).

        Raises:
            BrowserLaunchFailedError: If the underlying browser process
                failed to start, or its real DevTools endpoint never
                became reachable in time.
        """
        ...

    async def capture_screenshot(self, handle: PageHandle) -> bytes:
        """Return a real PNG screenshot of ``handle``'s current page content.

        Args:
            handle: A real, still-live page returned by :meth:`open_page`.

        Returns:
            Real, real PNG image bytes.

        Raises:
            BrowserActionFailedError: If ``handle``'s underlying
                browser process or page is no longer reachable, or the
                real CDP call itself failed.
        """
        ...

    async def query_dom(self, handle: PageHandle, selector: str) -> str | None:
        """Return the outer HTML of the first real element matching ``selector``, or None.

        Args:
            handle: A real, still-live page returned by :meth:`open_page`.
            selector: A real CSS selector, evaluated against the page's
                current, live DOM (not a static snapshot).

        Returns:
            The matched element's real outer HTML, or ``None`` if no
            element in the page's current DOM matches ``selector`` --
            a real, expected outcome, not an error.

        Raises:
            BrowserActionFailedError: If ``handle``'s underlying
                browser process or page is no longer reachable, or the
                real CDP call itself failed.
        """
        ...

    async def close(self, handle: PageHandle) -> None:
        """Terminate ``handle``'s underlying real browser subprocess.

        A no-op, not an error, if the process is already gone --
        mirroring this project's own general "tearing down something
        already torn down is not a failure" convention. Every real
        page returned by :meth:`open_page` must eventually be closed by
        its own caller; nothing in this port closes one automatically.
        """
        ...
