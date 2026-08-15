"""Adapters implementing jarvis.ports.tts.TtsPort.

:class:`PiperTtsAdapter` wraps ``piper-tts`` (OHF-Voice/piper1-gpl,
package name ``piper-tts`` on PyPI -- verified empirically against the
live PyPI API and the project's own README/VOICES.md before being
hardcoded here, not assumed from the architecture doc's text alone:
the doc itself notes the original Piper repo was archived and this OHF
fork is the correct, current successor). CPU-only, ONNX-based (its
core dependencies are ``onnxruntime`` and ``pathvalidate`` -- ``torch``
is only pulled in behind the package's own ``train`` extra, which this
project never installs).

The voice model (``en_US-lessac-medium``, a `.onnx` file plus a
`.onnx.json` config) is fetched from Hugging Face
(``rhasspy/piper-voices``), pinned to release tag ``v1.0.0`` -- not
``main`` -- per the same force-push-avoidance reasoning as
adapters/vad.py's Silero model pin. Verified fetchable (live HEAD
requests confirmed HTTP 200 and real byte sizes) before being
hardcoded, not guessed.

``piper.voice.AudioChunk`` (the type ``PiperVoice.synthesize()``
yields, one per sentence) is a different, unrelated type from this
project's own ``jarvis.domain.audio.AudioChunk`` -- the same name,
by coincidence, for a similar but distinct concept. Never imported
directly here by that name for exactly that reason; only its
``audio_int16_bytes``/``sample_rate`` attributes are read, via
attribute access, not an import that could collide.

Testability seam, matching every other real-hardware adapter in this
project (``score_source``, ``predict_fn``): :class:`PiperTtsAdapter`
accepts an injectable ``speak_fn`` -- given text, returns the fully
assembled ``(samples, sample_rate)`` pair. Unit tests inject a fake one
to verify :meth:`speak` correctly wraps the result in an
:class:`~jarvis.domain.audio.AudioStream`, with no real model. The
default, real implementation (:meth:`PiperTtsAdapter._default_speak`)
is the one genuinely untested-by-design piece. Unlike the
microphone-dependent adapters, this one doesn't need real hardware to
run (CPU-only synthesis), but it does need a ~63MB model download on
first use, which is not appropriate to do unconditionally in CI; its
correctness is proven by manual verification instead (see
docs/architecture/m1-voice-architecture.md section 10).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import platformdirs

from jarvis.domain.audio import AudioStream

if TYPE_CHECKING:
    from collections.abc import Callable

    SpeakFn = Callable[[str], "tuple[bytes, int]"]

_VOICE_TAG = "v1.0.0"
_MODEL_FILENAME = "en_US-lessac-medium.onnx"
_CONFIG_FILENAME = "en_US-lessac-medium.onnx.json"
_MODEL_URL = (
    f"https://huggingface.co/rhasspy/piper-voices/resolve/"
    f"{_VOICE_TAG}/en/en_US/lessac/medium/{_MODEL_FILENAME}"
)
_CONFIG_URL = (
    f"https://huggingface.co/rhasspy/piper-voices/resolve/"
    f"{_VOICE_TAG}/en/en_US/lessac/medium/{_CONFIG_FILENAME}"
)


def _model_cache_dir() -> Path:
    """Return the persistent, platform-appropriate cache directory for the TTS voice model."""
    return Path(platformdirs.user_cache_dir("jarvis")) / "tts_models"


def _ensure_model_files() -> tuple[Path, Path]:
    """Download the voice model and its config if not already cached, return their paths."""
    import urllib.request  # noqa: PLC0415 -- deliberately lazy, see module docstring

    cache_dir = _model_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    model_path = cache_dir / _MODEL_FILENAME
    config_path = cache_dir / _CONFIG_FILENAME
    if not model_path.exists():
        urllib.request.urlretrieve(_MODEL_URL, model_path)
    if not config_path.exists():
        urllib.request.urlretrieve(_CONFIG_URL, config_path)
    return model_path, config_path


class PiperTtsAdapter:
    """Text-to-speech backed by piper-tts's CPU/ONNX voice synthesis."""

    def __init__(self, speak_fn: SpeakFn | None = None) -> None:
        """Store configuration only. No I/O happens at construction time.

        Args:
            speak_fn: Given text, returns the fully assembled
                ``(samples, sample_rate)`` pair. Defaults to a real
                implementation running piper-tts. Overridable for
                tests, exactly as other adapters' hardware-touching
                seams are.
        """
        self._speak_fn: SpeakFn = speak_fn or self._default_speak
        self._voice: object | None = None

    async def speak(self, text: str) -> AudioStream:
        """Synthesize ``text`` and return the resulting audio, ready for playback."""
        samples, sample_rate = self._speak_fn(text)
        return AudioStream(samples=samples, sample_rate=sample_rate)

    def _default_speak(self, text: str) -> tuple[bytes, int]:
        self._ensure_model_loaded()
        assert self._voice is not None  # noqa: S101 -- narrows Optional for mypy, not a runtime guard

        chunks = list(self._voice.synthesize(text))  # type: ignore[attr-defined]
        # A valid sample rate is required even for empty text (no chunks
        # produced): the voice's own config exposes its native rate, so an
        # empty AudioStream is still well-formed, not a fabricated 0.
        sample_rate: int = self._voice.config.sample_rate  # type: ignore[attr-defined]
        samples = b"".join(chunk.audio_int16_bytes for chunk in chunks)
        return samples, sample_rate

    def _ensure_model_loaded(self) -> None:
        if self._voice is not None:
            return
        model_path, config_path = _ensure_model_files()

        from piper import PiperVoice  # noqa: PLC0415 -- deliberately lazy, see module docstring

        self._voice = PiperVoice.load(model_path, config_path=config_path)
