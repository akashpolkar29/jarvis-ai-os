# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "faster-whisper",
# ]
# ///
"""WP-19 stage 1: GPU/CUDA smoke test for faster-whisper's ctranslate2 backend.

Resolves the one known-risky assumption before any mic/wake-word complexity
is layered on top (see docs/architecture/m1-voice-architecture.md section 9):
ctranslate2 officially targets CUDA 12 + cuDNN 9, this machine has CUDA 13.2,
and NVIDIA's driver backward-compatibility model should make that fine
(ctranslate2's pip wheels bundle their own CUDA 12 runtime) -- but it's
unverified on this specific machine until this script runs clean.

Success = WhisperModel loads on cuda/float16 and transcribe() completes
without a CUDA/cuDNN exception. The transcript content of a zeroed (silent)
buffer is irrelevant -- this script only proves the GPU path doesn't crash.

Run with: uv run poc/wp19_01_gpu_smoke.py
"""

# ruff: noqa: T201, D103 -- disposable script: terminal output and a bare
# main() are the point, not library hygiene.
from __future__ import annotations

import numpy as np
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
SILENCE_DURATION_S = 3.0


def main() -> None:
    print("Loading WhisperModel('medium', device='cuda', compute_type='float16')...")
    model = WhisperModel("medium", device="cuda", compute_type="float16")

    silence = np.zeros(int(SAMPLE_RATE * SILENCE_DURATION_S), dtype=np.float32)

    print("Transcribing in-memory silence...")
    segments, info = model.transcribe(silence, language="en")
    list(segments)  # force generator evaluation so any error surfaces here

    print(f"OK -- detected language: {info.language} (p={info.language_probability:.3f})")
    print("GPU smoke test passed: no CUDA/cuDNN exception on load or transcribe.")


if __name__ == "__main__":
    main()
