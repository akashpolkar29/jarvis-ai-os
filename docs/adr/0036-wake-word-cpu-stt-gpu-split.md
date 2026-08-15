# ADR-0036: Continuous CPU wake-word detection, GPU speech-to-text only after a trigger

## Status

Accepted

## Date

2026-08-15

## Source

Work packages WP-19 (hardware/library proof-of-concept), WP-20 (WakeWordPort), WP-21 (VadPort/SttPort)

## Context

Always-on listening is a new, permanent privacy and resource surface (see the threat-model addition in section 5 of docs/architecture/m1-voice-architecture.md): wake-word detection has to run continuously, on-device, for as long as the process is alive, while speech-to-text is comparatively expensive and only ever needed for the few seconds of audio following an actual detection. Running both continuously would mean keeping a GPU model resident and evaluating it on every frame of silence the microphone ever captures -- wasteful, and a larger, more constant attack/privacy surface than necessary.

WP-19's hardware proof-of-concept surfaced two real, non-obvious problems that shaped which backend runs where:

1. openWakeWord's ONNX inference backend has a known, currently-open upstream bug (dscripka/openWakeWord#336): the mel-spectrogram-to-embedding pipeline produces near-zero scores regardless of audio content. Confirmed directly on this machine -- synthesized "hey jarvis" speech scored 0.9987 through the tflite backend versus near-zero through onnx, on identical audio. The tflite backend does not have this bug.
2. faster-whisper's backend (ctranslate2) targets CUDA 12; this machine has CUDA 13.2 installed. The first run failed with "Library libcublas.so.12 is not found or cannot be loaded," because an in-process `os.environ` assignment does not reliably reach ctranslate2's later `dlopen()` calls -- glibc's dynamic linker reads `LD_LIBRARY_PATH` at process startup, not on demand.

## Decision

Wake-word detection (`OpenWakeWordAdapter`, WP-20) runs continuously on CPU via openWakeWord's tflite inference path specifically (not ONNX, per the bug above), with `ai-edge-litert` providing the tflite interpreter (`tflite-runtime`'s only real PyPI wheel line stops at Python 3.11, unusable here) via a small local import shim. Cost is near-zero and constant, appropriate for something that must always be running.

Speech-to-text (`FasterWhisperAdapter`, WP-21) runs on GPU (`device="cuda"`, `compute_type="float16"`, model size `"medium"`), but is only ever invoked after a wake-word detection confirms -- never continuously, never on raw ambient audio. The CUDA library path mismatch is worked around by setting `LD_LIBRARY_PATH` to the `nvidia-cublas-cu12`/`nvidia-cudnn-cu12` package directories and then `os.execv()`-ing the current process, so the *new* process's dynamic linker sees the corrected path from the very start.

## Consequences

The GPU is only ever active for the few seconds after a genuine wake-word trigger, not continuously -- the privacy/resource surface of always-on listening is confined to the cheap, CPU-only, on-device wake-word stage. A real, stated architectural caveat carried forward from WP-21, not resolved here: `_ensure_cuda_library_path()`'s `os.execv()` restarts the *entire* process, which is fine as the first real thing a short-lived process does, but would silently destroy other in-flight state (e.g. an already-running wake-word listener) if `SttPort.transcribe()`'s first real call happens well into a long-running process's life. `kernel.voice_loop.run_voice_loop` (WP-25) is exactly such a long-running process; this fix's correct placement is at the very top of the real entrypoint (`jarvis listen`, WP-26), before anything else starts, which is where it needs to be revisited if a fresh CUDA library path is ever not already set in the environment `jarvis listen` is launched from.
