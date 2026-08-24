"""Desktop-control domain types: kept minimal, reusing existing provenance vocabulary.

:class:`WindowHandle` is the one new domain type M3 needs -- an opaque,
adapter-assigned identifier for a real window a
:class:`~jarvis.ports.desktop_window.DesktopWindowPort` adapter has
already found or launched. No new ``Trust``/``Classification``
vocabulary is introduced here: content read back through a window
(Terminal output, a web page) is tagged
``Trust.UNTRUSTED_EXTERNAL`` using the existing
``jarvis.domain.provenance`` types at the call site, exactly as
ADR-0011 already requires for this class of content.

:class:`SyntheticInputSession` is ADR-0047's own addition -- an opaque,
adapter-assigned handle for one open ``RemoteDesktop`` portal session,
matching :class:`WindowHandle`'s "opaque to callers" shape exactly, for
the same reason: only the adapter instance that opened a session knows
how to use it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WindowHandle:
    """An opaque, adapter-assigned identifier for one real, currently-known window.

    Attributes:
        value: The adapter's own identifier for this window. Only the
            adapter instance that issued a handle knows how to
            interpret it -- callers treat this as opaque. Real
            adapters are not required to make this valid beyond their
            own process lifetime (every JARVIS CLI invocation is
            already a fresh, separate process -- kernel/music.py's own
            precedent).
        app_id: The application identifier this window belongs to
            (the same value passed to
            ``DesktopWindowPort.find_or_launch``), kept alongside
            ``value`` so callers and audit logging can describe *which
            app* a handle refers to without decoding the adapter's own
            encoding.
    """

    value: str
    app_id: str

    def __post_init__(self) -> None:
        """Validate ``value`` and ``app_id`` are both non-empty, matching CapabilityId's rule."""
        if not self.value:
            msg = "WindowHandle.value must not be empty."
            raise ValueError(msg)
        if not self.app_id:
            msg = "WindowHandle.app_id must not be empty."
            raise ValueError(msg)


@dataclass(frozen=True)
class SyntheticInputSession:
    """An opaque, adapter-assigned identifier for one open RemoteDesktop portal session.

    Attributes:
        session_handle: The adapter's own identifier for this session
            (the portal's own session object path, for the real
            adapter) -- callers treat this as opaque, matching
            ``WindowHandle.value``.
        new_restore_token: A token the caller must persist via
            ``SecretPort.set_secret`` before this session is used
            again, or ``None`` if the portal issued no new token this
            time (ADR-0047: the portal rotates this token on every use
            it issues one for, never assumed stable across calls).
    """

    session_handle: str
    new_restore_token: str | None

    def __post_init__(self) -> None:
        """Validate session_handle is non-empty, matching WindowHandle's own rule."""
        if not self.session_handle:
            msg = "SyntheticInputSession.session_handle must not be empty."
            raise ValueError(msg)
