# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "faster-whisper",
#     "nvidia-cublas-cu12",
#     "nvidia-cudnn-cu12==9.*",
# ]
# ///
"""WP-19 stage 1: GPU/CUDA smoke test for faster-whisper's ctranslate2 backend.

Resolves the one known-risky assumption before any mic/wake-word complexity
is layered on top (see docs/architecture/m1-voice-architecture.md section 9):
ctranslate2 officially targets CUDA 12 + cuDNN 9, this machine has CUDA 13.2,
and NVIDIA's driver backward-compatibility model should make that fine
(ctranslate2's pip wheels bundle their own CUDA 12 runtime) -- but it's
unverified on this specific machine until this script runs clean.

First run on this machine failed with "Library libcublas.so.12 is not found
or cannot be loaded": the nvidia-cublas-cu12/nvidia-cudnn-cu12 wheels install
their .so files into site-packages, not onto the system loader's search
path, so ctranslate2's dlopen call can't find them unless LD_LIBRARY_PATH
points at those package directories. That is set programmatically below,
before faster_whisper/ctranslate2 are imported.

"No exception" alone is not accepted as proof of GPU execution here --
faster-whisper on a CUDA-13 host has been reported to sometimes fall back
to CPU silently. This script also samples `nvidia-smi` memory.used before
and after transcribe() and times the call, so a silent CPU fallback (VRAM
delta ~0, and/or transcribe() taking many seconds for 3s of silence) shows
up as an explicit warning rather than a false "OK".

Run with: uv run poc/wp19_01_gpu_smoke.py
"""

# ruff: noqa: T201, D103, TID251, S603, S606, E402 -- disposable script:
# terminal output, a bare main(), wall-clock time.monotonic() for latency
# measurement, a subprocess.run() with fully hardcoded arguments
# (nvidia-smi, resolved via shutil.which), a self-re-exec via os.execv()
# with sys.executable/sys.argv (trusted, not untrusted input), and imports
# after the LD_LIBRARY_PATH fixup (which must run before
# faster_whisper/ctranslate2 are imported) are the point here, not library
# hygiene, ClockPort injection, or untrusted-input hardening.
from __future__ import annotations

import os
import sys

import nvidia.cublas.lib
import nvidia.cudnn.lib

# These are PEP 420 namespace packages: no __file__, but __path__ works.
# An in-process os.environ assignment doesn't reliably reach ctranslate2's
# later dlopen() calls -- glibc's dynamic linker reads LD_LIBRARY_PATH at
# process startup, not on demand. So: set it, then self-re-exec via
# os.execv so the *new* process's linker sees it from the start. The
# membership check (not equality) guards against an infinite re-exec loop
# on the second pass, once these dirs are already part of the value.
cublas_dir = next(iter(nvidia.cublas.lib.__path__))
cudnn_dir = next(iter(nvidia.cudnn.lib.__path__))
current_ld_path = os.environ.get("LD_LIBRARY_PATH", "")

if cublas_dir not in current_ld_path or cudnn_dir not in current_ld_path:
    print(f"Re-exec-ing with LD_LIBRARY_PATH set to include: {cublas_dir} and {cudnn_dir}")
    os.environ["LD_LIBRARY_PATH"] = f"{cublas_dir}:{cudnn_dir}:{current_ld_path}"
    os.execv(sys.executable, [sys.executable, *sys.argv])

print(f"LD_LIBRARY_PATH confirmed set to: {os.environ['LD_LIBRARY_PATH']}")

import shutil
import subprocess
import time

import numpy as np
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
SILENCE_DURATION_S = 3.0
# 3s of silence should be near-instant on a real GPU; this is a heuristic
# trip-wire for "suspiciously slow, might actually be running on CPU", not
# a hard proof either way -- the VRAM delta below is the stronger signal.
CPU_LATENCY_SUSPICION_THRESHOLD_S = 5.0


def _nvidia_smi_used_memory_mib() -> int | None:
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        print("nvidia-smi not found on PATH")
        return None
    try:
        result = subprocess.run(
            [nvidia_smi, "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"nvidia-smi query failed: {exc}")
        return None
    return int(result.stdout.strip().splitlines()[0])


def main() -> None:
    print("Loading WhisperModel('medium', device='cuda', compute_type='float16')...")
    model = WhisperModel("medium", device="cuda", compute_type="float16")

    silence = np.zeros(int(SAMPLE_RATE * SILENCE_DURATION_S), dtype=np.float32)

    baseline_mib = _nvidia_smi_used_memory_mib()
    print(f"nvidia-smi memory.used before call 1: {baseline_mib} MiB")

    print("Transcribing in-memory silence (call 1, includes CUDA/cuDNN warmup)...")
    start = time.monotonic()
    segments, info = model.transcribe(silence, language="en")
    list(segments)  # force generator evaluation so any error surfaces here
    elapsed_call1_s = time.monotonic() - start

    between_mib = _nvidia_smi_used_memory_mib()
    print(f"nvidia-smi memory.used between call 1 and call 2: {between_mib} MiB")
    print(f"call 1 wall time: {elapsed_call1_s:.2f}s for {SILENCE_DURATION_S:.0f}s of audio")

    print("Transcribing in-memory silence (call 2, steady-state)...")
    start = time.monotonic()
    segments2, _info2 = model.transcribe(silence, language="en")
    list(segments2)  # force generator evaluation so any error surfaces here
    elapsed_call2_s = time.monotonic() - start

    after_mib = _nvidia_smi_used_memory_mib()
    print(f"nvidia-smi memory.used after call 2: {after_mib} MiB")
    print(f"call 2 wall time: {elapsed_call2_s:.2f}s for {SILENCE_DURATION_S:.0f}s of audio")
    print(f"Detected language: {info.language} (p={info.language_probability:.3f})")

    gpu_confirmed = True

    if baseline_mib is not None and after_mib is not None:
        delta_mib = after_mib - baseline_mib
        print(f"VRAM delta (before call 1 -> after call 2): {delta_mib} MiB")
        if delta_mib <= 0:
            gpu_confirmed = False
            print(
                "WARNING: VRAM usage did not rise -- this may mean the model is NOT "
                "actually running on GPU despite device='cuda'."
            )
    else:
        gpu_confirmed = False
        print("WARNING: could not read nvidia-smi memory usage -- GPU usage unconfirmed.")

    if elapsed_call2_s > CPU_LATENCY_SUSPICION_THRESHOLD_S:
        gpu_confirmed = False
        print(
            f"WARNING: call 2 (steady-state) took {elapsed_call2_s:.2f}s for "
            f"{SILENCE_DURATION_S:.0f}s of silence -- slow enough to suggest CPU "
            "execution despite device='cuda'. Call 1 includes warmup cost and is "
            "not the steady-state signal."
        )

    if gpu_confirmed:
        print(
            "PASS: no CUDA/cuDNN exception, VRAM rose, steady-state (call 2) "
            "latency consistent with GPU."
        )
    else:
        print("INCONCLUSIVE: ran without exception, but GPU execution is NOT confirmed.")


if __name__ == "__main__":
    main()
