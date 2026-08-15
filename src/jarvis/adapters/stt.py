"""Adapters implementing jarvis.ports.stt.SttPort.

:class:`FasterWhisperAdapter` wraps faster-whisper's ``WhisperModel``
("medium", ``device="cuda"``, ``compute_type="float16"`` -- decided in
WP-19/WP-20, not re-decided here).

Ports directly from WP-19 (poc/wp19_01_gpu_smoke.py), not re-derived:
the LD_LIBRARY_PATH self-re-exec fix for ctranslate2. faster-whisper's
first run on this machine failed with "Library libcublas.so.12 is not
found or cannot be loaded" -- ctranslate2 (faster-whisper's backend)
officially targets CUDA 12, this machine has CUDA 13.2, and an
in-process ``os.environ`` assignment doesn't reliably reach
ctranslate2's later ``dlopen()`` calls, since glibc's dynamic linker
reads ``LD_LIBRARY_PATH`` at process startup, not on demand. The fix:
set ``LD_LIBRARY_PATH`` to the ``nvidia-cublas-cu12``/``nvidia-cudnn-
cu12`` package directories, then ``os.execv()`` so the *new* process's
linker sees it from the start.

Architectural caveat, stated plainly, not papered over: ``os.execv()``
restarts the *entire* process, not just this adapter. WP-19's scripts
and WP-20's wake-word adapter could afford to run this fix as the
first real thing a process does (wake-word detection is plausibly
started at process startup). STT is different: once WP-25 actually
wires WakeWordPort -> VadPort -> SttPort together, ``transcribe()``'s
first real call could happen well into a long-running process's life,
by which point a wake-word listener may already be running. A lazy
re-exec at that point would restart the whole process and silently
destroy that other in-flight state, not just fix this adapter's CUDA
path. The correct place for this fix is once, at the very top of
whatever real entrypoint eventually embeds this adapter, before
anything else starts -- which is WP-25's concern (kernel/CLI changes
are out of this work package's scope) and needs to be resolved there,
not silently assumed away here. Ported as-is per instruction, flagged
rather than fixed, since fixing it means writing kernel code this WP
is explicitly not scoped to touch.

Testability seam, matching jarvis.adapters.wake_word/vad: the real
model-loading and re-exec logic lives entirely in
:meth:`FasterWhisperAdapter._ensure_model_loaded`, the one genuinely
untested-by-design piece -- it requires a real GPU and a real
ctranslate2/faster-whisper install, exactly what cannot be relied on
in CI. Its correctness is proven by manual verification instead (see
docs/architecture/m1-voice-architecture.md section 10).
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import numpy as np

from jarvis.domain.provenance import Provenance, Tainted
from jarvis.domain.transcript import Transcript

if TYPE_CHECKING:
    from jarvis.domain.audio import Segment

SAMPLE_RATE = 16000
INT16_FULL_SCALE = 32768.0
DEFAULT_MODEL_SIZE = "medium"


def _ensure_cuda_library_path() -> None:
    """Set LD_LIBRARY_PATH for ctranslate2's CUDA libraries, re-exec-ing if it isn't already set.

    See the module docstring for the full explanation and the process-
    wide-re-exec caveat. Must run before ``faster_whisper``/
    ``ctranslate2`` are imported. Ported directly from
    poc/wp19_01_gpu_smoke.py -- the membership check (not equality)
    guards against an infinite re-exec loop once these dirs are
    already part of the value, matching that script exactly.
    """
    import nvidia.cublas.lib  # noqa: PLC0415 -- deliberately lazy, see module docstring
    import nvidia.cudnn.lib  # noqa: PLC0415

    cublas_dir = next(iter(nvidia.cublas.lib.__path__))
    cudnn_dir = next(iter(nvidia.cudnn.lib.__path__))
    current_ld_path = os.environ.get("LD_LIBRARY_PATH", "")

    if cublas_dir not in current_ld_path or cudnn_dir not in current_ld_path:
        os.environ["LD_LIBRARY_PATH"] = f"{cublas_dir}:{cudnn_dir}:{current_ld_path}"
        os.execv(sys.executable, [sys.executable, *sys.argv])  # noqa: S606


class FasterWhisperAdapter:
    """Speech-to-text backed by faster-whisper's WhisperModel on CUDA."""

    def __init__(self, model_size: str = DEFAULT_MODEL_SIZE) -> None:
        """Store configuration only. No I/O happens at construction time.

        Args:
            model_size: The faster-whisper model size to load
                (default: "medium", per WP-19/WP-20's decision).
        """
        self._model_size = model_size
        self._model: object | None = None

    async def transcribe(self, audio: Segment) -> Tainted[Transcript]:
        """Transcribe ``audio`` and tag the result Provenance.user() (USER_DIRECT trust)."""
        if audio.sample_rate != SAMPLE_RATE:
            msg = (
                f"FasterWhisperAdapter only supports {SAMPLE_RATE}Hz audio, got {audio.sample_rate}"
            )
            raise ValueError(msg)

        self._ensure_model_loaded()
        assert self._model is not None  # noqa: S101 -- narrows Optional for mypy, not a runtime guard

        samples = np.frombuffer(audio.samples, dtype=np.int16).astype(np.float32) / (
            INT16_FULL_SCALE
        )
        segments, _info = self._model.transcribe(samples, language="en")  # type: ignore[attr-defined]
        text = "".join(segment.text for segment in segments).strip()
        return Tainted(Transcript(text=text), Provenance.user())

    def _ensure_model_loaded(self) -> None:
        if self._model is not None:
            return
        _ensure_cuda_library_path()

        from faster_whisper import WhisperModel  # noqa: PLC0415 -- deliberately lazy

        self._model = WhisperModel(self._model_size, device="cuda", compute_type="float16")
