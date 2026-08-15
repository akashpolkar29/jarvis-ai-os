"""Unit tests for jarvis.ui.confirm.dialog._is_genuine_physical_event.

This is the mechanical proof required by
docs/threat-model/v0.md section 5: a simulated/injected confirmation
-- a "clicked" handler invoked with no real Gdk.Event backing it,
exactly what an in-process ``button.emit("clicked")`` or
``button.activate()`` call produces -- must be rejected, not treated
as physical approval. No real GTK4/display is touched here: the
predicate is a plain function over a small duck-typed event shape (see
``_GdkEventLike`` in the module under test), so these tests run
without ``gi`` installed and without a display.
"""

from __future__ import annotations

from jarvis.ui.confirm.dialog import _is_genuine_physical_event


class _FakeDevice:
    """Stands in for a real Gdk.Device -- its identity is irrelevant, only its presence."""


class _FakeEventWithDevice:
    """Stands in for a genuine Gdk.Event carrying a real input device."""

    def get_device(self) -> object | None:
        """Return a non-None device, as a real hardware-sourced event would."""
        return _FakeDevice()


class _FakeEventWithNoDevice:
    """Stands in for whatever a non-genuine event report would carry: no device at all."""

    def get_device(self) -> object | None:
        """Return None, exactly as a device-less/synthetic report would."""
        return None


def test_a_missing_event_is_rejected() -> None:
    """No event at all -- exactly what an in-process signal emission produces -- is rejected.

    This is the direct case: calling a button's "clicked" handler via
    ``button.emit("clicked")``/``button.activate()`` rather than a real
    click leaves nothing for ``Gtk.get_current_event()`` to return.
    """
    assert _is_genuine_physical_event(None) is False


def test_an_event_with_no_device_is_rejected() -> None:
    """An event object present but reporting no backing device is rejected."""
    assert _is_genuine_physical_event(_FakeEventWithNoDevice()) is False


def test_an_event_with_a_real_device_is_accepted() -> None:
    """A genuine event, backed by a real input device, is accepted."""
    assert _is_genuine_physical_event(_FakeEventWithDevice()) is True
