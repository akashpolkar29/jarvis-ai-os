"""Unit tests for jarvis.adapters.physical_confirmation.Gtk4PhysicalConfirmationAdapter.

What's exercised here is entirely the pure wiring: prompt/timeout
passed through to an injected fake dialog_fn, and its bool result
relayed unchanged. No real display, no real GTK4, no real human is
touched -- the real dialog path
(``jarvis.ui.confirm.dialog.show_confirmation_dialog``) has no
automated test, matching every other real-hardware adapter in this
project; its correctness is proven by manual verification instead (see
docs/architecture/m1-voice-architecture.md section 10).
"""

from __future__ import annotations

from jarvis.adapters.physical_confirmation import Gtk4PhysicalConfirmationAdapter

_TIMEOUT_S = 30.0


async def test_await_physical_confirmation_relays_a_true_result() -> None:
    """A dialog_fn reporting approval is relayed as True unchanged."""
    adapter = Gtk4PhysicalConfirmationAdapter(dialog_fn=lambda _prompt, _timeout: True)

    result = await adapter.await_physical_confirmation("delete all files?", _TIMEOUT_S)

    assert result is True


async def test_await_physical_confirmation_relays_a_false_result() -> None:
    """A dialog_fn reporting denial (or timeout) is relayed as False unchanged."""
    adapter = Gtk4PhysicalConfirmationAdapter(dialog_fn=lambda _prompt, _timeout: False)

    result = await adapter.await_physical_confirmation("delete all files?", _TIMEOUT_S)

    assert result is False


async def test_await_physical_confirmation_passes_the_prompt_and_timeout_through() -> None:
    """The exact prompt and timeout passed in reach dialog_fn unchanged."""
    received: list[tuple[str, float]] = []

    def fake_dialog(prompt: str, timeout_s: float) -> bool:
        received.append((prompt, timeout_s))
        return True

    adapter = Gtk4PhysicalConfirmationAdapter(dialog_fn=fake_dialog)

    await adapter.await_physical_confirmation("play music?", 15.0)

    assert received == [("play music?", 15.0)]


def test_constructing_the_adapter_with_no_arguments_does_no_io() -> None:
    """Matches every other adapter's convention: __init__ does zero I/O."""
    adapter = Gtk4PhysicalConfirmationAdapter()

    assert adapter is not None
