"""Adapters implementing jarvis.ports.wake_word.WakeWordPort.

:class:`OpenWakeWordAdapter` wraps openWakeWord's tflite inference path
to produce a continuous stream of :class:`~jarvis.domain.wake_word.WakeEvent`.
Three things had to be worked around to get here, all discovered and
empirically verified during WP-19's proof-of-concept (see
``poc/wp19_03_wakeword_smoke.py`` for the full derivation) and ported
directly here, not re-derived:

1. openWakeWord's ONNX inference backend has a known, currently-open
   upstream bug (dscripka/openWakeWord#336): the mel-spectrogram-to-
   embedding pipeline produces near-zero scores regardless of audio
   content. The tflite backend does not have this bug -- WP-19 confirmed
   this directly (synthesized "hey jarvis" speech scored 0.9987 through
   tflite versus near-zero through onnx, on identical audio).
2. openwakeword>=0.5.0 declares a hard, unconditional-on-Linux
   dependency on ``tflite-runtime``, whose last-ever PyPI wheel supports
   up to Python 3.11 only. ``pyproject.toml``'s ``[tool.uv].override-
   dependencies`` replaces that requirement with an always-false
   marker (empirically verified via ``uv lock``/``uv sync`` against
   this real project, not assumed to transfer from the PEP 723 script
   context it was first proven in).
3. openwakeword's tflite code path still does ``import tflite_runtime.
   interpreter``, which no longer exists as a real installable package
   for this platform/Python combination. ``ai-edge-litert`` (Google's
   actively maintained successor, a real project dependency) provides
   the same Interpreter API; :func:`_ensure_tflite_shim` makes
   ``import tflite_runtime.interpreter`` resolve to it via a small
   local shim package, created fresh at process runtime and never
   pip-installed.

The three ``.tflite`` model files openwakeword's wheel does not bundle
are downloaded from openWakeWord's v0.5.1 GitHub release on first run
and cached under a persistent, platform-appropriate user cache
directory (``platformdirs``), not a temp directory -- unlike WP-19's
throwaway scripts, this is a real, repeatedly-run adapter, and
re-downloading ~3.5MB of model weights on every process start would be
wasteful.

Lazy imports, deliberately: ``sounddevice``, ``openwakeword``, and the
shim setup are imported only inside :meth:`OpenWakeWordAdapter._default_score_source`,
not at module level. Merely importing this module (e.g. via
``jarvis.adapters``'s package ``__init__``) must not mutate ``sys.path``
or touch the filesystem -- that side effect is deferred until the real
hardware path is actually used, matching this codebase's existing "no
I/O at construction time" convention (see
``jarvis.adapters.media_player``).

Testability seam, matching ``jarvis.adapters.media_player``'s
``_send_method_call_over_dbus``: :class:`OpenWakeWordAdapter` accepts an
injectable ``frame_source``, a zero-argument callable returning an
async iterator of ``(score, raw_chunk)`` pairs -- one per captured
frame. Unit tests inject a fake one to verify :class:`_WakeWordDebouncer`'s
firing behavior and the ring-buffer/post-trigger-capture wiring
deterministically -- no real microphone, no real model, no real
hardware at all. The default, real implementation,
:meth:`OpenWakeWordAdapter._default_frame_source`, is the one
genuinely untested-by-design piece: it requires a live microphone,
exactly what cannot be relied on in CI. Its correctness is proven by
manual verification instead (see
``docs/architecture/m1-voice-architecture.md`` section 10).

Known simplification: ``_default_frame_source`` performs blocking
hardware I/O (``sounddevice``'s blocking read API) and CPU-bound model
inference synchronously inside an ``async def`` generator, with no
``await`` points -- it blocks the event loop while running, rather than
yielding control via a thread executor. This matches WP-19's proven,
manually-verified synchronous design exactly; making it genuinely
non-blocking is real future work (likely at WP-25's kernel wiring,
where the actual concurrency model across wake-word/VAD/STT/TTS gets
decided), not attempted speculatively here.

ADR-0033 (WP-25 finding): :meth:`stream` -- not ``frame_source`` --
owns the :class:`_AudioRingBuffer` (previously constructed, pushed to,
and never read inside what was ``_default_score_source``, a dead seam
WP-20 apparently anticipated but never wired up). On a confirmed
detection, :meth:`stream` snapshots the ring buffer (pre-trigger
context) and then keeps pulling further ``(score, chunk)`` pairs from
the *same* frame-source iterator -- not a new one, not a second
capture -- for up to ``post_trigger_capture_s`` more seconds (default
:data:`POST_TRIGGER_CAPTURE_DURATION_S`, deliberately configurable per
instance so tests can set it to ``0.0`` and keep exercising the
debouncer/event-count logic without needing unrealistically long fake
frame lists), without running the debouncer on those frames -- a
detection is already confirmed; this window is purely "keep recording
the command," not "also watch for a new wake word." The combined
audio becomes the yielded :class:`~jarvis.domain.wake_word.WakeEvent`'s
``audio`` field. If the frame source is exhausted mid-window (a fake
source in a test, or a real stream closing), whatever was captured so
far is used rather than raising -- the same graceful-degradation
choice a real, closing microphone stream would need regardless.
"""

from __future__ import annotations

import logging
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import platformdirs

from jarvis.domain.audio import AudioChunk
from jarvis.domain.wake_word import WakeEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    FrameSource = Callable[[], AsyncIterator[tuple[float, np.ndarray]]]

_logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
WAKEWORD_CHUNK_SAMPLES = 1280  # openWakeWord expects 80ms chunks at 16kHz
DEFAULT_THRESHOLD = 0.5
REQUIRED_CONSECUTIVE_FRAMES = 2
RING_BUFFER_DURATION_S = 5.0
POST_TRIGGER_CAPTURE_DURATION_S = 3.0  # see ADR-0033 -- a considered default, not a measured one

_MODEL_RELEASE_BASE = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1"
_MODEL_FILENAMES = ("melspectrogram.tflite", "embedding_model.tflite", "hey_jarvis_v0.1.tflite")
_WAKE_WORD_LABEL = "hey_jarvis"


def _model_cache_dir() -> Path:
    """Return the persistent, platform-appropriate cache directory for wake-word model files.

    Unlike WP-19's proof-of-concept scripts (which used a temp
    directory that doesn't survive a reboot), this adapter is real,
    repeatedly-run application code: re-downloading these files every
    process start would be wasteful, not just slow.
    """
    return Path(platformdirs.user_cache_dir("jarvis")) / "wake_word_models"


def _ensure_model_files() -> dict[str, Path]:
    """Download the three .tflite model files if not already cached, return their paths."""
    import urllib.request  # noqa: PLC0415 -- deliberately lazy, see module docstring

    cache_dir = _model_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name in _MODEL_FILENAMES:
        path = cache_dir / name
        if not path.exists():
            _logger.info("Downloading wake-word model file: %s", name)
            urllib.request.urlretrieve(f"{_MODEL_RELEASE_BASE}/{name}", path)  # noqa: S310
        paths[name] = path
    return paths


_shim_ready = False


def _ensure_tflite_shim() -> None:
    """Make ``import tflite_runtime.interpreter`` resolve to ai_edge_litert, idempotently.

    openwakeword's tflite code path does ``import tflite_runtime.
    interpreter`` unconditionally; no real ``tflite-runtime`` package is
    installed (see the module docstring for why). This creates a
    minimal local package -- one empty ``__init__.py``, one
    ``interpreter.py`` re-exporting ``ai_edge_litert.interpreter.
    Interpreter`` -- and puts it at the front of ``sys.path``. Must run
    before ``openwakeword`` (or anything under it) is imported. Safe to
    call more than once: a module-level flag prevents creating a second,
    wasted shim directory on repeated calls within the same process.
    """
    global _shim_ready  # noqa: PLW0603 -- deliberate, simple idempotency guard, not general
    # mutable global state: this function's entire contract is "safe to call repeatedly,
    # does the real work exactly once."
    if _shim_ready:
        return

    import sys  # noqa: PLC0415
    import tempfile  # noqa: PLC0415

    shim_dir = Path(tempfile.mkdtemp(prefix="jarvis_wake_word_tflite_shim_"))
    shim_pkg = shim_dir / "tflite_runtime"
    shim_pkg.mkdir()
    (shim_pkg / "__init__.py").write_text("")
    (shim_pkg / "interpreter.py").write_text("from ai_edge_litert.interpreter import Interpreter\n")
    sys.path.insert(0, str(shim_dir))
    _shim_ready = True


def _resolve_default_input_device_name() -> str:
    """Return the name of sounddevice's currently-resolved default input device.

    Logged every time the real hardware path starts: PipeWire can
    silently route the "default" input to an unexpected physical
    device (WP-19 found it defaulting to a USB webcam's microphone
    instead of the laptop's internal mic, with zero visibility into
    what had happened) -- this makes that resolution visible instead of
    silent.
    """
    import sounddevice as sd  # noqa: PLC0415 -- deliberately lazy, see module docstring

    device_info = sd.query_devices(kind="input")
    name = device_info["name"]
    return str(name)


def _score_for_wake_word(predictions: dict[str, float]) -> float:
    """Extract this adapter's wake word's score from openWakeWord's raw predict() output.

    Matches on substring, not exact key equality: openWakeWord's
    prediction-dict key naming has varied across versions/model
    filenames (e.g. ``hey_jarvis`` vs ``hey_jarvis_v0.1``) -- WP-19 hit
    this directly. Returns 0.0 (not a KeyError) if no matching key is
    present, since a missing key and a confidently-absent detection are
    not meaningfully different to this adapter's caller.
    """
    for key, score in predictions.items():
        if _WAKE_WORD_LABEL in key.lower():
            return score
    return 0.0


class _AudioRingBuffer:
    """A bounded, in-memory-only buffer of recently captured raw audio.

    Never touches disk under any circumstance -- there is no file I/O
    anywhere in this class -- matching ADR-0018 ("audio is never
    persisted to disk"), extended here to cover transient buffering
    during wake-word evaluation itself, not just longer-term storage.
    Oldest chunks are evicted once the buffered duration would exceed
    ``max_duration_s``; the newest chunk is never evicted, even if it
    alone exceeds the configured duration, so the buffer is never left
    empty after a successful push.
    """

    def __init__(self, max_duration_s: float, sample_rate: int) -> None:
        """Configure the buffer's capacity. Allocates no audio storage yet."""
        self._max_samples = int(max_duration_s * sample_rate)
        self._chunks: deque[np.ndarray] = deque()
        self._total_samples = 0

    def push(self, chunk: np.ndarray) -> None:
        """Append ``chunk``, evicting the oldest buffered chunks past the configured duration."""
        self._chunks.append(chunk)
        self._total_samples += chunk.shape[0]
        while self._total_samples > self._max_samples and len(self._chunks) > 1:
            evicted = self._chunks.popleft()
            self._total_samples -= evicted.shape[0]

    def snapshot(self) -> np.ndarray:
        """Return everything currently buffered, oldest-first, as one concatenated array."""
        if not self._chunks:
            return np.empty(0, dtype=np.int16)
        return np.concatenate(list(self._chunks))

    def __len__(self) -> int:
        """Return the number of samples currently buffered."""
        return self._total_samples


class _WakeWordDebouncer:
    """Pure, stateful interpretation of a stream of per-frame scores into WakeEvent firings.

    Requires ``required_consecutive_frames`` consecutive frames scoring
    at or above ``threshold`` before confirming a detection -- WP-19
    found real speech producing noisy, fluctuating per-frame scores
    (roughly 0.15-0.81 across genuine utterances of the same phrase),
    so a single-frame threshold crossing alone is too fragile a signal.
    The counter resets to zero on any sub-threshold frame. It also
    resets to zero immediately after confirming a detection (rather
    than continuing to count past the requirement), so one utterance
    that stays at or above threshold across many consecutive frames
    fires exactly once, not once per frame -- a fresh streak is
    required before the next firing.
    """

    def __init__(
        self, threshold: float, required_consecutive_frames: int = REQUIRED_CONSECUTIVE_FRAMES
    ) -> None:
        """Configure the debounce parameters. Starts with no accumulated streak."""
        self._threshold = threshold
        self._required = required_consecutive_frames
        self._consecutive = 0

    def observe(self, score: float) -> bool:
        """Feed one frame's score. Return True exactly on the frame confirming a detection."""
        if score < self._threshold:
            self._consecutive = 0
            return False
        self._consecutive += 1
        if self._consecutive >= self._required:
            self._consecutive = 0
            return True
        return False


class OpenWakeWordAdapter:
    """Continuous wake-word detection backed by openWakeWord's tflite inference path."""

    def __init__(
        self,
        frame_source: FrameSource | None = None,
        threshold: float = DEFAULT_THRESHOLD,
        post_trigger_capture_s: float = POST_TRIGGER_CAPTURE_DURATION_S,
    ) -> None:
        """Store configuration only. No I/O happens at construction time.

        Args:
            frame_source: A zero-argument callable returning an async
                iterator of ``(score, raw_chunk)`` pairs, one per
                captured frame. Defaults to a real implementation
                reading the system's default microphone through the
                tflite model. Overridable for tests, exactly as
                ``MprisMediaPlayerAdapter``'s ``send_method_call`` is.
            threshold: The minimum per-frame score treated as a
                candidate detection. Passed to the debouncer that
                :meth:`stream` constructs fresh on each call.
            post_trigger_capture_s: How many additional seconds of
                audio :meth:`stream` captures after a confirmed
                detection, before yielding the WakeEvent (ADR-0033).
                Defaults to the real, production value; tests set this
                to ``0.0`` to keep exercising firing/event-count logic
                without needing long fake frame lists.
        """
        self._frame_source: FrameSource = frame_source or self._default_frame_source
        self._threshold = threshold
        self._post_trigger_capture_s = post_trigger_capture_s

    async def stream(self) -> AsyncIterator[WakeEvent]:
        """Yield one WakeEvent per confirmed detection, each carrying the triggering audio.

        Runs until the caller stops iterating. See the module
        docstring (ADR-0033) for the ring-buffer/post-trigger-capture
        design this method owns.
        """
        debouncer = _WakeWordDebouncer(self._threshold)
        ring_buffer = _AudioRingBuffer(RING_BUFFER_DURATION_S, SAMPLE_RATE)
        frames = self._frame_source()

        async for score, chunk in frames:
            ring_buffer.push(chunk)
            if not debouncer.observe(score):
                continue

            pre_trigger_audio = ring_buffer.snapshot()
            post_trigger_target_samples = int(self._post_trigger_capture_s * SAMPLE_RATE)
            post_trigger_chunks: list[np.ndarray] = []
            captured_samples = 0
            while captured_samples < post_trigger_target_samples:
                try:
                    _next_score, next_chunk = await anext(frames)
                except StopAsyncIteration:
                    break
                ring_buffer.push(next_chunk)
                post_trigger_chunks.append(next_chunk)
                captured_samples += next_chunk.shape[0]

            combined = np.concatenate([pre_trigger_audio, *post_trigger_chunks])
            yield WakeEvent(
                score=score,
                audio=AudioChunk(
                    samples=combined.astype(np.int16).tobytes(), sample_rate=SAMPLE_RATE
                ),
            )

    async def _default_frame_source(self) -> AsyncIterator[tuple[float, np.ndarray]]:
        """The one real, untested-by-design piece: real mic -> real tflite model -> (score, chunk).

        See the module docstring for why this is not unit-tested and
        blocks the event loop while running. Ring-buffering (pre- and
        post-trigger audio) is :meth:`stream`'s responsibility, not
        this generator's -- see ADR-0033.
        """
        _ensure_tflite_shim()
        model_paths = _ensure_model_files()

        import sounddevice as sd  # noqa: PLC0415 -- deliberately lazy, see module docstring
        from openwakeword.model import Model  # noqa: PLC0415

        device_name = _resolve_default_input_device_name()
        _logger.info("OpenWakeWordAdapter: resolved default input device: %s", device_name)

        model = Model(
            wakeword_models=[str(model_paths["hey_jarvis_v0.1.tflite"])],
            inference_framework="tflite",
            melspec_model_path=str(model_paths["melspectrogram.tflite"]),
            embedding_model_path=str(model_paths["embedding_model.tflite"]),
        )

        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=WAKEWORD_CHUNK_SAMPLES
        ) as stream:
            while True:
                chunk, _overflowed = stream.read(WAKEWORD_CHUNK_SAMPLES)
                chunk = chunk.reshape(-1)
                predictions = model.predict(chunk)
                yield _score_for_wake_word(predictions), chunk
