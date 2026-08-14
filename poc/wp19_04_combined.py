# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "faster-whisper",
#     "nvidia-cublas-cu12",
#     "nvidia-cudnn-cu12==9.*",
#     "openwakeword==0.6.0",
#     "ai-edge-litert",
#     "sounddevice",
#     "numpy",
# ]
#
# [tool.uv]
# override-dependencies = ["tflite-runtime; python_version < '0'"]
# ///
"""WP-19 stage 4 (combined): the actual WP-19 deliverable.

Continuous wake-word listening (CPU, tflite backend) -> on trigger, capture
~4.5s of command audio into memory -> convert to the format faster-whisper
expects (mono, 16kHz, float32, normalized to [-1, 1]) -> transcribe
directly on the numpy array, no temp file, no disk write anywhere in the
loop -> print the transcript -> loop back to listening.

This is the first script in the work package combining the fixes worked
out separately and independently verified in stage 1 (poc/wp19_01_gpu_smoke.py)
and stage 3 (poc/wp19_03_wakeword_smoke.py) -- ported directly from both,
not re-derived, since each was already proven working on its own:

From stage 1: the LD_LIBRARY_PATH self-re-exec fix for ctranslate2.
nvidia-cublas-cu12/nvidia-cudnn-cu12 install their .so files into
site-packages, not the system loader's search path, and an in-process
os.environ assignment doesn't reliably reach ctranslate2's later dlopen()
calls (glibc reads LD_LIBRARY_PATH at process startup). So: set it, then
self-re-exec via os.execv so the *new* process's linker sees it from the
start. Must run before faster_whisper/ctranslate2 are imported.

From stage 3: the tflite backend for openWakeWord, needed because the onnx
backend has a known, currently-open upstream bug (dscripka/openWakeWord#336)
that produces near-zero scores regardless of audio content. Three pieces,
port directly: (a) `[tool.uv].override-dependencies` to satisfy
openwakeword>=0.5.0's unconditional-on-Linux `tflite-runtime` requirement
with an always-false marker, since tflite-runtime has no cp312 wheel at
all; (b) a local `tflite_runtime` -> `ai_edge_litert` shim package, created
fresh at runtime (never pip-installed), since openwakeword's tflite code
path still does `import tflite_runtime.interpreter`; (c) the three
.tflite model files openwakeword's wheel doesn't bundle, downloaded from
the v0.5.1 GitHub release and cached under the system temp dir.

A real countdown (3...2...1..., actual time.sleep(1) calls, flushed
output) runs once at startup, after both models finish loading, so there's
an unambiguous, synchronized moment for knowing detection is actually
live -- the same problem a missing countdown caused during stage 3's
manual verification (repeated near-silent captures with no timing cue).
Because listening here is continuous rather than a single fixed window,
the countdown only needs to run once, not before every utterance; a
periodic `score=...` line during listening and an explicit "Listening
again" message after each transcript serve as the ongoing "ready" signal
the fixed-window stage-3 script didn't need.

Nothing is written to disk anywhere in the loop -- no capture, no
transcript, matching ADR-0036's spirit even though this script sits
outside its formal enforcement.

Run with: uv run poc/wp19_04_combined.py
"""

# ruff: noqa: T201, D103, TID251, S310, S606, E402 -- disposable script:
# terminal output, a bare main(), wall-clock time.monotonic() for a
# print-rate throttle, urlretrieve() against a hardcoded (not
# user-controlled) https:// GitHub release URL, a self-re-exec via
# os.execv() with sys.executable/sys.argv (trusted, not untrusted input),
# and imports after the LD_LIBRARY_PATH fixup and tflite shim setup (both
# of which must run before their respective libraries are imported) are
# the point here, not library hygiene, ClockPort injection, or
# untrusted-input hardening.
from __future__ import annotations

import os
import sys

import nvidia.cublas.lib
import nvidia.cudnn.lib

# See stage 1 (poc/wp19_01_gpu_smoke.py) for the full explanation of why
# this re-exec is necessary rather than just setting os.environ in place.
cublas_dir = next(iter(nvidia.cublas.lib.__path__))
cudnn_dir = next(iter(nvidia.cudnn.lib.__path__))
current_ld_path = os.environ.get("LD_LIBRARY_PATH", "")

if cublas_dir not in current_ld_path or cudnn_dir not in current_ld_path:
    print(f"Re-exec-ing with LD_LIBRARY_PATH set to include: {cublas_dir} and {cudnn_dir}")
    os.environ["LD_LIBRARY_PATH"] = f"{cublas_dir}:{cudnn_dir}:{current_ld_path}"
    os.execv(sys.executable, [sys.executable, *sys.argv])

print(f"LD_LIBRARY_PATH confirmed set to: {os.environ['LD_LIBRARY_PATH']}")

import tempfile
import time
import urllib.request
from pathlib import Path

# See stage 3 (poc/wp19_03_wakeword_smoke.py) for the full explanation of
# why this shim exists instead of a real tflite-runtime install.
_SHIM_DIR = Path(tempfile.mkdtemp(prefix="jarvis_wp19_tflite_shim_"))
_shim_pkg = _SHIM_DIR / "tflite_runtime"
_shim_pkg.mkdir()
(_shim_pkg / "__init__.py").write_text("")
(_shim_pkg / "interpreter.py").write_text("from ai_edge_litert.interpreter import Interpreter\n")
sys.path.insert(0, str(_SHIM_DIR))

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from openwakeword.model import Model

SAMPLE_RATE = 16000
WAKEWORD_CHUNK_SAMPLES = 1280  # openWakeWord expects 80ms chunks at 16kHz
DETECTION_THRESHOLD = 0.5
COMMAND_DURATION_S = 4.5
SCORE_PRINT_INTERVAL_S = 0.5
INT16_FULL_SCALE = 32768.0

MODEL_RELEASE_BASE = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1"
MODEL_FILENAMES = ("melspectrogram.tflite", "embedding_model.tflite", "hey_jarvis_v0.1.tflite")
MODEL_CACHE_DIR = Path(tempfile.gettempdir()) / "jarvis_wp19_tflite_models"


def _ensure_model_files() -> dict[str, Path]:
    MODEL_CACHE_DIR.mkdir(exist_ok=True)
    paths: dict[str, Path] = {}
    for name in MODEL_FILENAMES:
        path = MODEL_CACHE_DIR / name
        if not path.exists():
            print(f"Downloading {name}...")
            urllib.request.urlretrieve(f"{MODEL_RELEASE_BASE}/{name}", path)
        paths[name] = path
    return paths


def _score_for_hey_jarvis(predictions: dict[str, float]) -> float:
    for key, score in predictions.items():
        if "hey_jarvis" in key.lower():
            return score
    return 0.0


def _capture_command_audio(stream: sd.InputStream) -> np.ndarray:
    n_samples = int(COMMAND_DURATION_S * SAMPLE_RATE)
    audio, _ = stream.read(n_samples)
    return audio.reshape(-1)


def _to_whisper_input(int16_audio: np.ndarray) -> np.ndarray:
    # Passing raw int16 samples (or otherwise wrong dtype/scale) to
    # faster-whisper doesn't error -- it silently produces gibberish output.
    # This conversion (float32, normalized to [-1, 1]) is the one that matters.
    return int16_audio.astype(np.float32) / INT16_FULL_SCALE


def main() -> None:
    wakeword_paths = _ensure_model_files()
    print("Loading 'hey_jarvis' tflite wake-word model...")
    wakeword_model = Model(
        wakeword_models=[str(wakeword_paths["hey_jarvis_v0.1.tflite"])],
        inference_framework="tflite",
        melspec_model_path=str(wakeword_paths["melspectrogram.tflite"]),
        embedding_model_path=str(wakeword_paths["embedding_model.tflite"]),
    )

    print("Loading WhisperModel('medium', device='cuda', compute_type='float16')...")
    whisper_model = WhisperModel("medium", device="cuda", compute_type="float16")

    print("3...", flush=True)
    time.sleep(1)
    print("2...", flush=True)
    time.sleep(1)
    print("1...", flush=True)
    time.sleep(1)
    print("Listening for 'hey jarvis' NOW... (Ctrl+C to stop)", flush=True)

    last_print = 0.0

    with sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=WAKEWORD_CHUNK_SAMPLES
    ) as stream:
        try:
            while True:
                chunk, _ = stream.read(WAKEWORD_CHUNK_SAMPLES)
                score = _score_for_hey_jarvis(wakeword_model.predict(chunk.reshape(-1)))

                if score >= DETECTION_THRESHOLD:
                    print(f"DETECTED  score={score:.3f} -- listening for command...", flush=True)
                    command_audio = _to_whisper_input(_capture_command_audio(stream))

                    segments, _info = whisper_model.transcribe(command_audio, language="en")
                    transcript = "".join(segment.text for segment in segments).strip()
                    print(f"Transcript: {transcript!r}", flush=True)
                    print("Listening for 'hey jarvis' again... (Ctrl+C to stop)", flush=True)
                    continue

                now = time.monotonic()
                if now - last_print >= SCORE_PRINT_INTERVAL_S:
                    print(f"score={score:.3f}", flush=True)
                    last_print = now
        except KeyboardInterrupt:
            print("\nStopped.", flush=True)


if __name__ == "__main__":
    main()
