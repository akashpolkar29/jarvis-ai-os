"""Adapters implementing jarvis.ports.physical_confirmation.PhysicalConfirmationPort.

:class:`Gtk4PhysicalConfirmationAdapter` is the Finding 2 closure
(docs/threat-model/v0.md): the first ``PhysicalConfirmationPort``
implementation backed by a genuine physical action -- a keypress or
click on a real GTK4 dialog -- rather than a self-reported boolean.
See ``jarvis.ui.confirm.dialog`` for the dialog itself and the
event-genuineness check that makes "physical" a real, mechanically
enforced claim rather than just a UI convention.

Testability seam, matching every other real-hardware adapter in this
project (``jarvis.adapters.vad``/``stt``/``tts``): the real
dialog-showing call lives entirely in ``jarvis.ui.confirm``'s
``show_confirmation_dialog``, injected here as ``dialog_fn`` and
defaulted to the real one. Unit tests inject a fake to prove the pure
wiring (prompt/timeout passed through, the returned bool relayed
unchanged) without a display or a real human. The real path is
deliberately outside the automated suite -- proven by manual
verification only (see docs/architecture/m1-voice-architecture.md
section 10).

``await_physical_confirmation`` is declared ``async`` to satisfy
``PhysicalConfirmationPort``'s signature, but its body is synchronous,
same as ``FasterWhisperAdapter.transcribe`` and
``PiperTtsAdapter.speak``: this project does not offload blocking
hardware/UI calls onto a background thread, it simply blocks the
calling coroutine, matching those adapters' established convention.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    DialogFn = Callable[[str, float], bool]


def _default_dialog_fn(prompt: str, timeout_s: float) -> bool:
    from jarvis.ui.confirm import show_confirmation_dialog  # noqa: PLC0415 -- see module docstring

    return show_confirmation_dialog(prompt, timeout_s)


class Gtk4PhysicalConfirmationAdapter:
    """Physical confirmation backed by a real GTK4 dialog requiring a genuine keypress/click."""

    def __init__(self, dialog_fn: DialogFn | None = None) -> None:
        """Store the dialog function to use. No I/O happens at construction time.

        Args:
            dialog_fn: The function ``await_physical_confirmation``
                delegates to, defaulting to the real GTK4 dialog. Tests
                inject a fake here to prove the wiring without a
                display.
        """
        self._dialog_fn: DialogFn = dialog_fn or _default_dialog_fn

    async def await_physical_confirmation(self, prompt: str, timeout_s: float) -> bool:
        """Relay ``prompt``/``timeout_s`` to the dialog function and return its result unchanged."""
        return self._dialog_fn(prompt, timeout_s)
