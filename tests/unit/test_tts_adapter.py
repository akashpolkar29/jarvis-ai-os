"""Unit tests for jarvis.adapters.tts.PiperTtsAdapter.

What's exercised here is entirely the pure wiring: speak() wrapping an
injected fake speak_fn's result in an AudioStream. No real model, no
real hardware of any kind is touched -- the real synthesis path
(_default_speak, _ensure_model_loaded) has no automated test, matching
every other real-hardware adapter in this project; its correctness is
proven by manual verification instead (see
docs/architecture/m1-voice-architecture.md section 10).
"""

from __future__ import annotations

from jarvis.adapters.tts import PiperTtsAdapter

_SAMPLE_RATE = 22050


async def test_speak_wraps_the_speak_fn_result_in_an_audio_stream() -> None:
    """speak() returns an AudioStream carrying exactly the injected speak_fn's result."""
    fake_samples = b"\x01\x02\x03\x04"
    adapter = PiperTtsAdapter(speak_fn=lambda _text: (fake_samples, _SAMPLE_RATE))

    result = await adapter.speak("hello")

    assert result.samples == fake_samples
    assert result.sample_rate == _SAMPLE_RATE


async def test_speak_passes_the_requested_text_to_speak_fn() -> None:
    """The exact text passed to speak() reaches speak_fn unchanged."""
    received: list[str] = []

    def fake_speak(text: str) -> tuple[bytes, int]:
        received.append(text)
        return b"", _SAMPLE_RATE

    adapter = PiperTtsAdapter(speak_fn=fake_speak)

    await adapter.speak("play some music")

    assert received == ["play some music"]


async def test_speak_handles_an_empty_result() -> None:
    """A speak_fn returning empty samples still produces a valid, well-formed AudioStream."""
    adapter = PiperTtsAdapter(speak_fn=lambda _text: (b"", _SAMPLE_RATE))

    result = await adapter.speak("")

    assert result.samples == b""
    assert result.sample_rate == _SAMPLE_RATE


def test_constructing_the_adapter_with_no_arguments_does_no_io() -> None:
    """Matches every other adapter's convention: __init__ does zero I/O."""
    adapter = PiperTtsAdapter()

    assert adapter is not None
