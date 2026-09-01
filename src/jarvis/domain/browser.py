"""Browser-automation domain types: kept minimal, no new provenance vocabulary.

:class:`PageHandle` is the one new domain type M5's browser-automation
track needs -- an opaque-to-callers, adapter-assigned reference to one
real, CDP-controlled browser page. Unlike
:class:`~jarvis.domain.desktop.WindowHandle` (a single opaque ``str``
token an AT-SPI2 adapter interprets internally), a CDP page genuinely
needs several separate, real facts to be reachable again from a *fresh*
process: every ``authorize_and_*`` call in this codebase is already a
fresh, separate process (``kernel/ping.py``'s own precedent), so a
handle returned by one ``browser.open_page`` call must carry enough
information for a later, separate ``browser.screenshot``/
``browser.inspect_dom`` call -- a different process, with no shared
in-memory adapter state -- to reconnect to the *same* already-running,
real browser subprocess and the *same* real page/target inside it, and
for a later ``close()`` to tear down everything that call created, not
just the process.
Modeled as explicit, typed fields rather than one opaque encoded
string, matching this project's own general preference for real,
checkable structure over an adapter-private blob (:class:`~jarvis.domain.memory.MemoryRecord`'s
own four real fields, not one opaque encoding, is the same precedent).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageHandle:
    """A real, reconnectable reference to one CDP-controlled browser page.

    Attributes:
        debug_port: The real, live TCP port the browser's own
            DevTools/CDP HTTP+WebSocket endpoint is listening on, on
            ``127.0.0.1`` -- never exposed beyond localhost by this
            project's own real adapter (see
            ``jarvis.adapters.browser_automation``'s own docstring).
        target_id: The real, adapter-issued CDP target id for this
            specific page (from a real ``Target.createTarget`` call),
            used to reconnect to this exact page's own page-level
            WebSocket endpoint on a later, separate call.
        process_id: The real process id of the browser subprocess this
            page lives inside -- the one piece of state a caller needs
            to actually tear the browser process down again
            (mirroring :meth:`~jarvis.ports.sandbox.SandboxPort.launch`'s
            own "returns a real pid, caller's own responsibility to
            terminate it later" precedent).
        user_data_dir: The real, adapter-created temporary directory
            this browser subprocess was launched with (its own
            isolated profile, never the user's real one -- see
            ``jarvis.adapters.browser_automation``'s own module
            docstring). Carried here, not just used internally at
            launch time and discarded, so a real ``close()`` call can
            actually remove it again -- without this, every real
            ``open_page`` call would leak one real temporary directory
            on disk forever.

    Raises:
        ValueError: If ``target_id``/``user_data_dir`` is empty, or if
            ``debug_port``/``process_id`` is not a positive integer.
    """

    debug_port: int
    target_id: str
    process_id: int
    user_data_dir: str

    def __post_init__(self) -> None:
        """Validate every field is a real, positive/non-empty value."""
        if self.debug_port <= 0:
            msg = f"PageHandle.debug_port must be positive: {self.debug_port!r}"
            raise ValueError(msg)
        if not self.target_id:
            msg = "PageHandle.target_id must not be empty."
            raise ValueError(msg)
        if self.process_id <= 0:
            msg = f"PageHandle.process_id must be positive: {self.process_id!r}"
            raise ValueError(msg)
        if not self.user_data_dir:
            msg = "PageHandle.user_data_dir must not be empty."
            raise ValueError(msg)
