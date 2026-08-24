"""Adapters implementing jarvis.ports.desktop_window.DesktopWindowPort.

:class:`AtspiDesktopWindowAdapter` finds, focuses, types into, and
reads back text from real application windows via AT-SPI2
(https://docs.gtk.org/atspi2/), the same accessibility D-Bus service
GNOME's own screen reader uses -- reached here via the ``Atspi`` GI
typelib (``gi.require_version("Atspi", "2.0")``), not a new protocol.

**Real deviation from the design objective's stated mechanism ("portal
+ libei, X11 fallback, AT-SPI2"), decided during WP-43's feasibility
spike and logged here rather than silently substituted:** this adapter
uses AT-SPI2 exclusively, for two concrete reasons confirmed live on
the real development machine, not assumed:

1. ``gi.require_version("EIS", "1.0")`` raised ``ValueError: Namespace
   EIS not available`` -- the libei GI binding the original objective
   named is not installed here, and no bare ``libei`` Python module
   exists either. The design doc's own "Known risks" section already
   flagged "the libei Python binding situation is young"; WP-43 found
   it is not merely young but simply absent on this machine.
2. The Wayland ``org.freedesktop.portal.RemoteDesktop`` interface
   *is* present (confirmed via a real, safe ``gdbus introspect`` --
   read-only, no session created), but actually calling
   ``CreateSession`` on it triggers a real system permission dialog on
   the user's live screen. Doing that during an unattended run, with
   no one present to answer it, is exactly the kind of uninvited
   real-desktop side effect this work package's hard-stop rule exists
   to avoid -- so it was never invoked, live or otherwise, during this
   pass.

AT-SPI2, by contrast, is a plain D-Bus service (confirmed reachable:
``Atspi.get_desktop(0)`` enumerated 18 real accessible top-level
applications during the spike, read-only, no dialog, no state change)
and is **display-server-agnostic** -- it works identically over
Wayland and X11, since it never touches the compositor directly. This
is a genuine simplification the original "X11 fallback" framing didn't
anticipate: there is no separate X11 code path to write here at all.

Real, honestly-flagged limitation, also found live during WP-43: this
mechanism's reach depends on the *caller's* own D-Bus/AppArmor
confinement, not just the target app's. A real AT-SPI2 ``GetItems``
call against Brave's accessible tree, issued from a snap-confined
caller process, was denied by the snap D-Bus proxy
(``An AppArmor policy prevents this sender from sending this message
to this recipient``) -- independent of any policy on Brave itself.
Whether a real, eventually-packaged JARVIS process is itself
snap-confined when this code actually runs is not something this pass
controls or can verify in advance; flagged as a real, environment-
dependent risk rather than assumed away.

Testability seam, matching ``jarvis.adapters.media_player``'s own
precedent exactly: the real AT-SPI2 GI calls live in small,
injectable, untested-by-design functions
(``_atspi_find_app``/``_atspi_focus``/``_atspi_type_text``/
``_atspi_read_text``/``_launch_subprocess``), each requiring a live
accessibility bus and a real target application neither CI nor this
unattended pass can rely on. Unit tests fake all five and exercise
only this adapter's own dispatch logic (handle-token bookkeeping,
which error type each failure mode becomes) -- real, but real about
what "real" covers here: **live focus/type_text/read_visible_text
against an actual running application window was never exercised in
this pass**, matching M1 tracker #19's and M2's ``family_b``'s own
honesty pattern for a real capability that is code-complete but not
live-verified.
"""

from __future__ import annotations

import subprocess
import time
from typing import TYPE_CHECKING, Any, cast

from jarvis.domain.desktop import WindowHandle
from jarvis.ports.desktop_window import WindowActionFailedError, WindowNotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable

    FindAppFn = Callable[[str], object | None]
    FocusFn = Callable[[object], bool]
    TypeTextFn = Callable[[object, str], bool]
    ReadTextFn = Callable[[object], "str | None"]
    LaunchFn = Callable[[tuple[str, ...]], None]
    SleepFn = Callable[[float], None]

_LAUNCH_POLL_ATTEMPTS = 10
_LAUNCH_POLL_INTERVAL_SECONDS = 0.5


def _atspi_find_app(app_id: str) -> object | None:
    """Search the real AT-SPI2 desktop tree for an app whose name contains ``app_id``.

    The one real, untested-by-design piece of this module (see the
    module docstring) -- requires a live accessibility bus. Matching
    is a case-insensitive substring match against each top-level
    application's own ``get_name()``, the same loose matching
    ``docker``/``git`` CLI subprocess adapters use for their own
    caller-supplied identifiers: no registry of exact expected names is
    maintained here, since AT-SPI2's own naming (e.g. "code" for VS
    Code, confirmed live during WP-43's spike) is already close enough
    to each app's own ``app_id`` to match directly.

    The GI ``Atspi`` typelib is untyped (see ``pyproject.toml``'s
    ``gi.*`` mypy override), so every accessible object handled in this
    module is genuinely ``Any`` at the type-checker level -- cast to
    ``object`` only at the point each function returns, matching this
    port's own "a handle/accessible is opaque to callers" contract.
    """
    import gi  # noqa: PLC0415 -- lazy, matching every other real-hardware adapter's own convention

    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi  # noqa: PLC0415

    Atspi.set_timeout(2000, 0)
    desktop = Atspi.get_desktop(0)
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        name = app.get_name() if app is not None else None
        if name and app_id.lower() in name.lower():
            return cast("object", app)
    return None


def _launch_subprocess(command: tuple[str, ...]) -> None:
    """Launch ``command`` as a real, detached subprocess and return immediately.

    Not awaited: callers poll for the resulting window via
    :func:`_atspi_find_app` afterward (real apps take real, variable
    time to register with the accessibility bus after starting).
    """
    subprocess.Popen(  # noqa: S603 -- command is caller-supplied config, not untrusted text
        command, start_new_session=True
    )


def _atspi_focus(app: object) -> bool:
    """Try Component.grab_focus(), then Action "activate", on the real accessible ``app``.

    Real, untested-by-design (see module docstring). Returns ``False``
    rather than raising when neither interface is available or the
    call itself fails -- the adapter's own dispatch logic converts a
    ``False`` into :class:`~jarvis.ports.desktop_window.WindowActionFailedError`.
    """
    import gi  # noqa: PLC0415

    gi.require_version("Atspi", "2.0")
    node: Any = app

    try:
        component = node.get_component_iface()
        if component is not None:
            component.grab_focus()
            return True
    except Exception:  # noqa: S110 -- fall through to the Action-based attempt below
        pass
    try:
        action = node.get_action_iface()
        if action is None:
            return False
        for i in range(action.get_n_actions()):
            if action.get_action_name(i) == "activate":
                action.do_action(i)
                return True
    except Exception:
        return False
    return False


def _find_focused_editable(app: object) -> object | None:
    """Depth-first search for a FOCUSED descendant exposing the EditableText interface."""
    import gi  # noqa: PLC0415

    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi  # noqa: PLC0415

    stack: list[Any] = [app]
    while stack:
        node = stack.pop()
        try:
            states = node.get_state_set()
            is_focused = states is not None and states.contains(Atspi.StateType.FOCUSED)
        except AttributeError:
            is_focused = False
        if is_focused:
            try:
                editable = node.get_editable_text_iface()
            except AttributeError:
                editable = None
            if editable is not None:
                return cast("object", editable)
        try:
            child_count = node.get_child_count()
        except AttributeError:
            child_count = 0
        stack.extend(node.get_child_at_index(i) for i in range(child_count))
    return None


def _atspi_type_text(app: object, text: str) -> bool:
    """Insert ``text`` into whichever FOCUSED descendant of ``app`` exposes EditableText.

    Real, untested-by-design (see module docstring). Uses AT-SPI2's
    ``EditableText.insert_text`` directly on the accessible object --
    setting the object's own text content, rather than synthesizing
    keyboard events -- since no synthetic-input mechanism (libei, the
    RemoteDesktop portal) was available or safe to use during this pass
    (see module docstring). Returns ``False`` if no focused editable
    descendant is found.
    """
    editable = _find_focused_editable(app)
    if editable is None:
        return False
    try:
        cast("Any", editable).insert_text(0, text, len(text))
    except Exception:
        return False
    return True


def _atspi_read_text(app: object) -> str | None:
    """Best-effort: return ``app``'s own Text-interface content, or ``None`` if unavailable.

    Real, untested-by-design (see module docstring). Only checks
    ``app`` itself, not descendants -- Terminal's real output-capture
    need (the one caller that genuinely uses this) targets a terminal
    emulator's own top-level accessible object, per WP-43's finding
    that AT-SPI2 support for this is app-specific and was not,
    itself, live-confirmed for any specific terminal emulator during
    this pass.
    """
    node: Any = app
    try:
        text_iface = node.get_text_iface()
    except AttributeError:
        return None
    if text_iface is None:
        return None
    try:
        return str(text_iface.get_text(0, -1))
    except Exception:
        return None


class AtspiDesktopWindowAdapter:
    """Finds, focuses, types into, and reads back text from real windows via AT-SPI2."""

    # Five independent real-mechanism seams + sleep, each its own
    # testability point per the module docstring -- not accidental bloat.
    def __init__(  # noqa: PLR0913, PLR0917
        self,
        find_app: FindAppFn | None = None,
        launch: LaunchFn | None = None,
        focus_fn: FocusFn | None = None,
        type_text_fn: TypeTextFn | None = None,
        read_text_fn: ReadTextFn | None = None,
        sleep_fn: SleepFn | None = None,
    ) -> None:
        """Store the low-level functions this adapter dispatches to. No I/O at construction time.

        Args:
            find_app: Given an app_id, returns a real accessible object
                or None. Defaults to the real AT-SPI2 implementation.
            launch: Given a command, launches it as a real subprocess.
                Defaults to the real implementation.
            focus_fn: Given a real accessible object, focuses it and
                returns whether that succeeded. Defaults to the real
                implementation.
            type_text_fn: Given a real accessible object and text,
                types the text and returns whether that succeeded.
                Defaults to the real implementation.
            read_text_fn: Given a real accessible object, returns its
                visible text or None. Defaults to the real
                implementation.
            sleep_fn: Called between launch-discovery poll attempts.
                Defaults to real ``time.sleep``. Tests inject a no-op
                to avoid a real, multi-second wait.
        """
        self._find_app: FindAppFn = find_app or _atspi_find_app
        self._launch: LaunchFn = launch or _launch_subprocess
        self._focus_fn: FocusFn = focus_fn or _atspi_focus
        self._type_text_fn: TypeTextFn = type_text_fn or _atspi_type_text
        self._read_text_fn: ReadTextFn = read_text_fn or _atspi_read_text
        self._sleep_fn: SleepFn = sleep_fn or time.sleep
        self._handles: dict[str, object] = {}

    def find_or_launch(
        self, app_id: str, launch_command: tuple[str, ...] | None = None
    ) -> WindowHandle:
        """Find a running window for ``app_id``, launching it via ``launch_command`` if not found.

        Raises:
            WindowNotFoundError: If no window is found and either no
                ``launch_command`` was given, or launching it still
                produced no discoverable window after polling.
        """
        app = self._find_app(app_id)
        if app is None and launch_command is not None:
            self._launch(launch_command)
            for _ in range(_LAUNCH_POLL_ATTEMPTS):
                self._sleep_fn(_LAUNCH_POLL_INTERVAL_SECONDS)
                app = self._find_app(app_id)
                if app is not None:
                    break
        if app is None:
            msg = f"No window found for app_id {app_id!r}."
            raise WindowNotFoundError(msg)
        token = f"{app_id}:{id(app)}"
        self._handles[token] = app
        return WindowHandle(value=token, app_id=app_id)

    def focus(self, handle: WindowHandle) -> None:
        """Focus the real window ``handle`` refers to.

        Raises:
            WindowActionFailedError: If ``handle`` is unknown to this
                adapter instance, or the underlying focus action failed.
        """
        app = self._resolve(handle)
        if not self._focus_fn(app):
            msg = f"Focusing window for {handle.app_id!r} failed."
            raise WindowActionFailedError(msg)

    def type_text(self, handle: WindowHandle, text: str) -> None:
        """Type ``text`` into ``handle``'s window's currently-focused editable control.

        Raises:
            WindowActionFailedError: If ``handle`` is unknown to this
                adapter instance, or no editable control could be
                found to receive ``text``.
        """
        app = self._resolve(handle)
        if not self._type_text_fn(app, text):
            msg = f"Typing into window for {handle.app_id!r} failed: no editable control found."
            raise WindowActionFailedError(msg)

    def read_visible_text(self, handle: WindowHandle) -> str | None:
        """Best-effort: return ``handle``'s window's visible text, or ``None``.

        Raises:
            WindowActionFailedError: If ``handle`` is unknown to this
                adapter instance.
        """
        app = self._resolve(handle)
        return self._read_text_fn(app)

    def _resolve(self, handle: WindowHandle) -> object:
        """Look ``handle`` up in this instance's own handle table.

        Raises:
            WindowActionFailedError: If ``handle`` was not issued by
                this adapter instance (or this instance has since been
                discarded) -- a handle has no meaning outside the
                adapter instance that created it.
        """
        try:
            return self._handles[handle.value]
        except KeyError:
            msg = f"WindowHandle {handle.value!r} is not known to this adapter instance."
            raise WindowActionFailedError(msg) from None
