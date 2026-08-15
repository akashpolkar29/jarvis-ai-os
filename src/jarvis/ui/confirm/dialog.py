"""The GTK4 confirmation dialog: the actual physical-keypress UI (WP-24, Finding 2 closure).

First real UI code in this project
(docs/architecture/m1-voice-architecture.md section 7). Deliberately
isolated in ``jarvis.ui``, importing nothing from any other ``jarvis``
package (import-linter contract "C5 ui privilege" enforces this): it
is a pure prompt-in/bool-out rendering leaf that
``jarvis.adapters.physical_confirmation.Gtk4PhysicalConfirmationAdapter``
calls into, never the other way around.

Why the event-genuineness check matters (ADR-0013, ADR-0041): GTK4's
own signal machinery lets any code in the *same process* fire a
button's "clicked" signal directly (``button.emit("clicked")``,
``button.activate()``), and such a programmatic emission carries no
real ``Gdk.Event`` at all -- there is nothing in flight for the
triggering ``Gtk.EventController`` to report via
``get_current_event()``. A confirmation only counts if a real event,
attributed to a real input device, backs it; a click handled with no
such event (exactly what an in-process synthetic call produces) is
silently ignored, not treated as a decision.
``_is_genuine_physical_event`` is the mechanical form of that rule,
and ``tests/unit/test_confirmation_dialog.py`` proves it rejects both
a missing event and a device-less one. Confirmed against a real
GTK4 4.14 / PyGObject 3.56 install: approve/deny are wired via a
``Gtk.GestureClick`` added to each button rather than the button's own
"clicked" signal, because the module-level ``Gtk.get_current_event()``
this project's architecture doc assumed does not exist in this GTK4
version -- ``EventController.get_current_event()`` (available on any
gesture/controller instance) is the real, working API, confirmed via
manual verification (poc/wp24_verify_dialog.py) rather than assumed.

Scope, stated honestly: this defends against software-only attempts to
fake a confirmation from within the process (or a fabricated event
object passed some other way) -- not against an attacker who already
has root or ``/dev/uinput`` access on the machine, which is a
strictly stronger capability than voice or network access. That
matches this project's own threat model: MANUAL_ONLY is not claimed to
be bulletproof against an attacker with full control of the session,
only against voice/recording/remote-triggered confirmation.

The real dialog-showing path (``show_confirmation_dialog``) is
deliberately outside the automated test suite -- it needs a real
display and a real human at the keyboard -- and is proven by manual
verification instead, matching every other real-hardware adapter in
this project (see docs/architecture/m1-voice-architecture.md
section 10). ``gi``/GTK are imported lazily, only inside
``show_confirmation_dialog``, so importing this module does no I/O and
requires no display.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable


class _GdkEventLike(Protocol):
    """The one piece of ``Gdk.Event`` this module needs -- enough to type-check the predicate."""

    def get_device(self) -> object | None: ...


def _is_genuine_physical_event(event: _GdkEventLike | None) -> bool:
    """Return whether ``event`` came from a real input device, not a programmatic signal emission.

    See the module docstring for why this specific check (event
    present, and its device present) is what actually enforces "a
    human pressed something" rather than "some code called the
    handler".
    """
    return event is not None and event.get_device() is not None


def show_confirmation_dialog(prompt: str, timeout_s: float) -> bool:
    """Show a modal GTK4 dialog asking the user to physically approve ``prompt``.

    Blocks the calling thread until the user clicks Approve or Deny,
    or ``timeout_s`` elapses with no genuine physical response. Denies
    by default on timeout or on any non-genuine (programmatic) click,
    matching MANUAL_ONLY's fail-closed contract.

    Never automated, never testable without a real display and a real
    human at the keyboard -- see the module docstring.
    """
    import gi  # noqa: PLC0415 -- deliberately lazy, see module docstring

    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk  # noqa: PLC0415

    app = Gtk.Application(application_id="ai.jarvis.confirm")
    result: list[bool] = []

    def _finish(approved: bool, window: Gtk.ApplicationWindow) -> None:
        if not result:
            result.append(approved)
        window.close()
        app.quit()

    def _on_activate(application: Gtk.Application) -> None:
        window = Gtk.ApplicationWindow(application=application, title="JARVIS: confirm action")
        window.set_default_size(420, 160)
        window.set_modal(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.append(Gtk.Label(label=prompt, wrap=True))

        button_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        deny_button = Gtk.Button(label="Deny")
        approve_button = Gtk.Button(label="Approve")
        button_row.append(deny_button)
        button_row.append(approve_button)
        box.append(button_row)
        window.set_child(box)

        def _wire_genuine_click(button: Gtk.Button, on_genuine_click: Callable[[], None]) -> None:
            # A Gtk.GestureClick, not the button's own "clicked" signal:
            # EventController.get_current_event() is the confirmed-working
            # way to recover the triggering Gdk.Event in this GTK4 version
            # (see module docstring -- Gtk.get_current_event() does not
            # exist here). Gestures coexist with the button's normal
            # rendering/state; nothing about the button's own behavior is
            # removed, only how *this module* decides a click was genuine.
            gesture = Gtk.GestureClick()

            def _on_pressed(
                controller: Gtk.GestureClick, _n_press: int, _x: float, _y: float
            ) -> None:
                # Claim the sequence: GtkButton runs its own internal click
                # gesture on this same widget, and without an explicit claim
                # here, this added gesture loses that arbitration -- it gets
                # "pressed" but is cancelled before "released" ever fires.
                # Confirmed via manual verification (poc/wp24_verify_dialog.py)
                # that claiming does not affect the button's own visual
                # pressed/hover feedback.
                controller.set_state(Gtk.EventSequenceState.CLAIMED)

            def _on_released(
                controller: Gtk.GestureClick, _n_press: int, _x: float, _y: float
            ) -> None:
                if _is_genuine_physical_event(controller.get_current_event()):
                    on_genuine_click()

            gesture.connect("pressed", _on_pressed)
            gesture.connect("released", _on_released)
            button.add_controller(gesture)

        _wire_genuine_click(approve_button, lambda: _finish(True, window))
        _wire_genuine_click(deny_button, lambda: _finish(False, window))

        def _on_timeout() -> bool:
            _finish(False, window)
            return bool(GLib.SOURCE_REMOVE)

        GLib.timeout_add(int(timeout_s * 1000), _on_timeout)
        window.present()

    app.connect("activate", _on_activate)
    app.run(None)
    return result[0] if result else False
