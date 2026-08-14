# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "openwakeword==0.6.0",
#     "ai-edge-litert",
#     "sounddevice",
#     "numpy",
# ]
#
# [tool.uv]
# override-dependencies = ["tflite-runtime; python_version < '0'"]
# ///
"""WP-19 stage 3: openWakeWord smoke test on live microphone audio (tflite backend).

Supersedes an earlier ONNX-backed version of this script entirely. That
version's scores stayed near-zero (~0.0001-0.001) on every real human
recording all session, including ones that sounded like clear speech on
playback -- eventually traced to a known, currently-open upstream bug in
openWakeWord's ONNX inference path (dscripka/openWakeWord#336): the
mel-spectrogram-to-embedding pipeline produces near-zero scores regardless
of audio content, on any platform, when using the onnx backend. Verified
during diagnosis: synthesized "hey jarvis" speech (espeak-ng) scored 0.9987
through this exact tflite pipeline, and near-zero through the onnx one --
confirming the fix, not just a plausible theory.

Three things had to be worked around to get here, all verified empirically
(not assumed) before landing:

1. openwakeword>=0.5.0 (needed for the tflite backend) declares a hard,
   unconditional dependency on `tflite-runtime` on Linux -- and
   tflite-runtime's last-ever PyPI wheel only supports up to Python 3.11,
   never 3.12. `[tool.uv].override-dependencies` above replaces that
   requirement with an always-false marker, which is not a version pin
   trick -- it makes uv treat the requirement as never applicable, so
   resolution succeeds without installing (or needing) a real
   tflite-runtime distribution at all.
2. openwakeword's tflite code path still does `import tflite_runtime.
   interpreter`, which no longer exists as a real installable package for
   this platform/Python combination. `ai-edge-litert` (Google's actively
   maintained successor, with a real cp312 Linux wheel) provides the same
   Interpreter API. A tiny local shim package, created fresh at runtime
   below (never installed via pip), makes `import tflite_runtime.
   interpreter` resolve to `ai_edge_litert.interpreter` instead.
3. The three .tflite model files openwakeword's PyPI wheel does not bundle
   (melspectrogram.tflite, embedding_model.tflite, hey_jarvis_v0.1.tflite)
   are downloaded from openWakeWord's v0.5.1 GitHub release on first run
   and cached under the system temp directory for subsequent runs.

A real countdown (3...2...1...Recording NOW, with actual time.sleep(1)
calls and flushed output) precedes the capture -- earlier attempts without
one repeatedly captured near-silence (peak amplitude ~0.1-0.2%) because
there was no synchronized cue for when recording actually started.

The captured audio is written to a temporary WAV file (openWakeWord's
predict_clip(), the mechanism verified during diagnosis, takes a file path,
not an in-memory array) so its path can be printed for manual playback
verification; it is not deleted automatically, unlike every other script in
this work package, specifically so it can be checked by ear if a score is
ambiguous. Delete it yourself when done -- see the printed path.

Run with: uv run poc/wp19_03_wakeword_smoke.py
"""

# ruff: noqa: T201, D103, E402, S310 -- disposable script: terminal output,
# a bare main(), imports after the tflite_runtime shim setup (which must
# run before openwakeword is imported), and urlopen() against a hardcoded,
# not user-controlled, https:// GitHub release URL are the point here, not
# library hygiene or untrusted-input hardening.
from __future__ import annotations

import os
import sys
import tempfile
import time
import urllib.request
import wave
from pathlib import Path

_SHIM_DIR = Path(tempfile.mkdtemp(prefix="jarvis_wp19_tflite_shim_"))
_shim_pkg = _SHIM_DIR / "tflite_runtime"
_shim_pkg.mkdir()
(_shim_pkg / "__init__.py").write_text("")
(_shim_pkg / "interpreter.py").write_text("from ai_edge_litert.interpreter import Interpreter\n")
sys.path.insert(0, str(_SHIM_DIR))

import numpy as np
import sounddevice as sd
from openwakeword.model import Model

SAMPLE_RATE = 16000
CAPTURE_DURATION_S = 4.0
DETECTION_THRESHOLD = 0.5

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


def main() -> None:
    model_paths = _ensure_model_files()
    print("Loading 'hey_jarvis' tflite model...")
    model = Model(
        wakeword_models=[str(model_paths["hey_jarvis_v0.1.tflite"])],
        inference_framework="tflite",
        melspec_model_path=str(model_paths["melspectrogram.tflite"]),
        embedding_model_path=str(model_paths["embedding_model.tflite"]),
    )

    print("3...", flush=True)
    time.sleep(1)
    print("2...", flush=True)
    time.sleep(1)
    print("1...", flush=True)
    time.sleep(1)
    print("Recording NOW", flush=True)

    audio = sd.rec(
        int(CAPTURE_DURATION_S * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16"
    )
    sd.wait()
    samples = audio.reshape(-1)
    peak = int(np.abs(samples).max())
    print(f"Captured {samples.size} samples. Peak amplitude: {peak} / 32768 ({peak / 32768:.1%})")

    wav_fd, wav_path_str = tempfile.mkstemp(prefix="jarvis_wp19_capture_", suffix=".wav")
    os.close(wav_fd)
    wav_path = Path(wav_path_str)
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(samples.tobytes())
    print(f"Saved capture for playback verification: {wav_path}")

    result = model.predict_clip(str(wav_path))
    max_score = max(d["hey_jarvis_v0.1"] for d in result)
    print(f"RAW RESULT: {result}")
    print(f"MAX SCORE: {max_score}")
    if max_score >= DETECTION_THRESHOLD:
        print(f"DETECTED  max_score={max_score:.3f}")
    else:
        print(f"not detected  max_score={max_score:.3f}  threshold={DETECTION_THRESHOLD}")
    print(f"(WAV not deleted -- play it back with: aplay {wav_path})")


if __name__ == "__main__":
    main()
