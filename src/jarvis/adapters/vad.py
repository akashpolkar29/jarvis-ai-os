"""Adapters implementing jarvis.ports.vad.VadPort.

:class:`SileroVadAdapter` wraps Silero VAD's ONNX model directly via
``onnxruntime`` -- deliberately not the ``silero-vad`` PyPI package,
which pulls in ``torch``/``torchaudio`` even when only its ONNX
backend is used (its own ``Validator``/``OnnxWrapper`` classes still
import ``torch`` at module level and convert every array through
``torch.Tensor``, regardless of ``onnx=True``). A minimal, torch-free
inference wrapper is written here instead, following the same pattern
already used for the tflite wake-word model in WP-20
(adapters/wake_word.py).

The model file (``silero_vad.onnx``) is fetched from Silero VAD's own
GitHub repo (github.com/snakers4/silero-vad, ``src/silero_vad/data/``)
rather than a copy bundled inside another package -- verified fetchable
(a live HEAD request confirmed HTTP 200 and the exact byte size
reported by GitHub's API) before this URL was hardcoded, not guessed.
There is no per-tag release asset the way openWakeWord's models are
distributed, so the download URL is pinned to a specific commit SHA
(``master``'s HEAD at the time this was written) rather than the
``master`` branch name itself -- this removes the force-push risk
entirely, rather than merely documenting it as accepted. Re-pinning to
a newer SHA is a deliberate, reviewed action if Silero ever ships a
model update worth picking up; it does not happen automatically.

Two things verified directly against the downloaded model and Silero's
own reference implementation (``src/silero_vad/utils_vad.py``) before
being hardcoded here, not assumed:

1. Fixed input window: 512 samples at 16kHz (256 at 8kHz, not used
   here -- this project is 16kHz throughout, per WP-19/WP-20). The
   ONNX graph itself declares dynamic shapes (``[None, None]``), so
   this is not enforced by the file format -- it is a correctness
   requirement of how the model was trained/is meant to be called,
   confirmed by reading Silero's own ``OnnxWrapper.__call__``.
2. The model is stateful/recurrent, not a stateless per-window
   classifier like openWakeWord's tflite model: each call must pass in
   a ``state`` tensor (shape ``[2, 1, 128]``) returned by the previous
   call, and a 64-sample "context" window (the tail of the previous
   window) must be prepended to each new 512-sample window before
   inference. :class:`_SileroVadModel` below replicates this exactly,
   in plain numpy -- not copying Silero's torch-based ``OnnxWrapper``
   wholesale, since none of its torch<->numpy conversions or
   dynamic-sample-rate-reset bookkeeping apply to this project's fixed
   16kHz, mono, single-buffer-per-call usage.

Segmentation logic (:class:`_VadSegmenter`) is a deliberately narrowed
adaptation of Silero's reference ``get_speech_timestamps`` hysteresis
algorithm: asymmetric enter/exit thresholds (``threshold`` /
``neg_threshold``), a minimum-silence-duration debounce before
confirming speech has ended, a minimum-speech-duration floor that
discards brief noise blips, and symmetric padding around each
confirmed segment. Deliberately not carried over: ``get_speech_
timestamps``'s ``max_speech_duration_s`` forced-splitting logic for
very long utterances, and its inter-segment padding-overlap
resolution -- both exist for long-form transcription (minutes of
continuous audio), not this project's actual use case (a single short
voice command captured after a wake-word trigger). Narrowing scope
here is a deliberate simplification, not an oversight -- see this
class's own docstring.

Testability seam, matching jarvis.adapters.wake_word's ``score_source``:
:class:`SileroVadAdapter` accepts an injectable ``predict_fn`` --
given one float32 window, returns a speech probability. Unit tests
inject a fake one to verify :class:`_VadSegmenter`'s segmentation
behavior deterministically -- no real model, no real hardware at all.
The default, real implementation (loading the ONNX model and running
real inference) is the one genuinely untested-by-design piece; its
correctness is proven by manual verification instead (see
docs/architecture/m1-voice-architecture.md section 10).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import platformdirs

from jarvis.domain.audio import AudioChunk, Segment

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    PredictFn = Callable[[np.ndarray], float]

SAMPLE_RATE = 16000
WINDOW_SIZE_SAMPLES = 512
CONTEXT_SIZE_SAMPLES = 64
INT16_FULL_SCALE = 32768.0

DEFAULT_THRESHOLD = 0.5
DEFAULT_MIN_SPEECH_DURATION_MS = 250
DEFAULT_MIN_SILENCE_DURATION_MS = 100
DEFAULT_SPEECH_PAD_MS = 30

# Pinned to a specific commit SHA, not the `master` branch name -- see the
# module docstring for why. This was `master`'s HEAD when pinned; verified
# fetchable via a live HEAD request (HTTP 200, matching content-length) before
# being hardcoded, not guessed.
_MODEL_COMMIT_SHA = "76e3dc408eb2a5c655c34e230d2d5459b4439daa"
_MODEL_URL = (
    f"https://raw.githubusercontent.com/snakers4/silero-vad/"
    f"{_MODEL_COMMIT_SHA}/src/silero_vad/data/silero_vad.onnx"
)
_MODEL_FILENAME = "silero_vad.onnx"


def _model_cache_dir() -> Path:
    """Return the persistent, platform-appropriate cache directory for the VAD model file."""
    return Path(platformdirs.user_cache_dir("jarvis")) / "vad_models"


def _ensure_model_file() -> Path:
    """Download silero_vad.onnx if not already cached, return its path."""
    import urllib.request  # noqa: PLC0415 -- deliberately lazy, see module docstring

    cache_dir = _model_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / _MODEL_FILENAME
    if not path.exists():
        urllib.request.urlretrieve(_MODEL_URL, path)
    return path


class _SileroVadModel:
    """A minimal, torch-free, stateful ONNX inference wrapper around Silero VAD.

    Replicates the exact call contract Silero's own ``OnnxWrapper``
    uses (context-prepending, recurrent state threading) in plain
    numpy, scoped to this project's fixed usage: mono, batch size 1,
    a single fixed sample rate for the lifetime of one instance. See
    the module docstring for why this exists instead of the
    ``silero-vad`` PyPI package's own wrapper.
    """

    def __init__(self, session: object, sample_rate: int = SAMPLE_RATE) -> None:
        """Wrap an already-constructed onnxruntime InferenceSession."""
        self._session = session
        self._sample_rate = sample_rate
        self._state: np.ndarray = np.zeros((2, 1, 128), dtype=np.float32)
        self._context: np.ndarray = np.zeros((1, CONTEXT_SIZE_SAMPLES), dtype=np.float32)

    def reset(self) -> None:
        """Clear recurrent state and context. Call once per independent audio buffer."""
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, CONTEXT_SIZE_SAMPLES), dtype=np.float32)

    def predict(self, window: np.ndarray) -> float:
        """Return the speech probability for one WINDOW_SIZE_SAMPLES float32 window.

        Threads recurrent state and the context prefix across calls --
        callers must feed windows from the same buffer in order,
        without skipping, and call :meth:`reset` between unrelated
        buffers.
        """
        x = np.concatenate([self._context, window.reshape(1, -1)], axis=1).astype(np.float32)
        ort_inputs = {
            "input": x,
            "state": self._state,
            "sr": np.array(self._sample_rate, dtype=np.int64),
        }
        out, state = self._session.run(None, ort_inputs)  # type: ignore[attr-defined]
        self._state = state
        self._context = x[:, -CONTEXT_SIZE_SAMPLES:]
        return float(out[0, 0])


class _VadSegmenter:
    """Pure, stateful interpretation of a stream of per-window speech probabilities.

    Adapted from Silero's reference ``get_speech_timestamps`` hysteresis
    logic -- see the module docstring for exactly what was narrowed and
    why. Feed it ``(window_index, speech_prob)`` pairs in order via
    :meth:`observe`; call :meth:`finalize` once after the last window
    to flush a still-open speech run at the end of the buffer. Sample
    offsets returned are already padded (``speech_pad_ms`` each side)
    and clamped to ``>= 0`` -- clamping to the buffer's actual length
    is the caller's responsibility, since this class has no notion of
    total buffer length until :meth:`finalize`.
    """

    def __init__(  # noqa: PLR0913, PLR0917 -- one parameter per Silero reference
        # get_speech_timestamps() tuning knob, matched 1:1 by design, not bundled into
        # a config object speculatively.
        self,
        threshold: float = DEFAULT_THRESHOLD,
        neg_threshold: float | None = None,
        min_speech_duration_ms: int = DEFAULT_MIN_SPEECH_DURATION_MS,
        min_silence_duration_ms: int = DEFAULT_MIN_SILENCE_DURATION_MS,
        speech_pad_ms: int = DEFAULT_SPEECH_PAD_MS,
        sample_rate: int = SAMPLE_RATE,
        window_size_samples: int = WINDOW_SIZE_SAMPLES,
    ) -> None:
        """Configure thresholds and duration floors. Starts with no open speech run."""
        self._threshold = threshold
        self._neg_threshold = (
            neg_threshold if neg_threshold is not None else max(threshold - 0.15, 0.01)
        )
        self._min_speech_samples = sample_rate * min_speech_duration_ms / 1000
        self._min_silence_samples = sample_rate * min_silence_duration_ms / 1000
        self._speech_pad_samples = sample_rate * speech_pad_ms / 1000
        self._window_size_samples = window_size_samples
        self._triggered = False
        self._speech_start = 0
        self._temp_end = 0

    def observe(self, window_index: int, speech_prob: float) -> tuple[int, int] | None:
        """Feed one window's speech probability. Return a padded (start, end) on confirmed end."""
        cur_sample = self._window_size_samples * window_index

        if speech_prob >= self._threshold and self._temp_end:
            # Speech resumed before min_silence_duration_ms elapsed: cancel the pending end.
            self._temp_end = 0

        if speech_prob >= self._threshold and not self._triggered:
            self._triggered = True
            self._speech_start = cur_sample
            return None

        if speech_prob < self._neg_threshold and self._triggered:
            if not self._temp_end:
                self._temp_end = cur_sample
            if cur_sample - self._temp_end < self._min_silence_samples:
                return None
            return self._confirm_end(self._temp_end)

        return None

    def finalize(self, total_samples: int) -> tuple[int, int] | None:
        """Flush a still-open speech run at end-of-buffer. Call once after the last window."""
        if self._triggered:
            return self._confirm_end(total_samples)
        return None

    def _confirm_end(self, end_sample: int) -> tuple[int, int] | None:
        start, end = self._speech_start, end_sample
        self._triggered = False
        self._temp_end = 0
        if end - start < self._min_speech_samples:
            return None  # too short: discard as a noise blip, not a real utterance
        padded_start = max(0, int(start - self._speech_pad_samples))
        padded_end = int(end + self._speech_pad_samples)
        return (padded_start, padded_end)


class SileroVadAdapter:
    """Voice-activity detection backed by Silero VAD's ONNX model."""

    def __init__(
        self, predict_fn: PredictFn | None = None, threshold: float = DEFAULT_THRESHOLD
    ) -> None:
        """Store configuration only. No I/O happens at construction time.

        Args:
            predict_fn: Given one float32 window, returns a speech
                probability. Defaults to a real implementation running
                the Silero VAD ONNX model. Overridable for tests,
                exactly as ``OpenWakeWordAdapter``'s ``score_source`` is.
            threshold: The minimum per-window probability treated as
                speech. Passed to the :class:`_VadSegmenter` this
                adapter constructs fresh for each :meth:`segment` call.
        """
        self._using_real_model = predict_fn is None
        self._predict_fn: PredictFn = predict_fn or self._default_predict_fn
        self._threshold = threshold
        self._model: _SileroVadModel | None = None

    async def segment(self, audio: AudioChunk) -> AsyncIterator[Segment]:
        """Yield each confirmed-speech Segment found in ``audio``."""
        if audio.sample_rate != SAMPLE_RATE:
            msg = f"SileroVadAdapter only supports {SAMPLE_RATE}Hz audio, got {audio.sample_rate}"
            raise ValueError(msg)

        if self._using_real_model:
            self._ensure_model_loaded()
            assert self._model is not None  # noqa: S101 -- narrows Optional for mypy, not a runtime guard
            self._model.reset()

        raw = np.frombuffer(audio.samples, dtype=np.int16)
        total_samples = raw.size
        pad_len = (-total_samples) % WINDOW_SIZE_SAMPLES
        padded = np.concatenate([raw, np.zeros(pad_len, dtype=np.int16)]) if pad_len else raw

        segmenter = _VadSegmenter(threshold=self._threshold)
        for window_index in range(padded.size // WINDOW_SIZE_SAMPLES):
            start = window_index * WINDOW_SIZE_SAMPLES
            window = padded[start : start + WINDOW_SIZE_SAMPLES].astype(np.float32) / (
                INT16_FULL_SCALE
            )
            speech_prob = self._predict_fn(window)
            bounds = segmenter.observe(window_index, speech_prob)
            if bounds is not None:
                yield self._to_segment(audio, bounds, total_samples)

        bounds = segmenter.finalize(total_samples)
        if bounds is not None:
            yield self._to_segment(audio, bounds, total_samples)

    @staticmethod
    def _to_segment(audio: AudioChunk, bounds: tuple[int, int], total_samples: int) -> Segment:
        start_sample, end_sample = bounds
        end_sample = min(end_sample, total_samples)
        start_byte, end_byte = start_sample * 2, end_sample * 2
        return Segment(samples=audio.samples[start_byte:end_byte], sample_rate=audio.sample_rate)

    def _ensure_model_loaded(self) -> None:
        if self._model is not None:
            return
        model_path = _ensure_model_file()

        import onnxruntime as ort  # noqa: PLC0415 -- deliberately lazy, see module docstring

        session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self._model = _SileroVadModel(session)

    def _default_predict_fn(self, window: np.ndarray) -> float:
        assert self._model is not None  # noqa: S101 -- narrows Optional for mypy, not a runtime guard
        return self._model.predict(window)
