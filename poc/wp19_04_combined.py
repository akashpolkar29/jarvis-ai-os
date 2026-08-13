# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "openwakeword",
#     "sounddevice",
#     "numpy",
#     "faster-whisper",
# ]
# ///
"""WP-19 stage 4 (combined): the actual WP-19 deliverable.

Continuous wake-word listening (CPU) -> on trigger, capture ~5s of command
audio into memory -> convert to the format faster-whisper expects (mono,
16kHz, float32, normalized to [-1, 1]) -> transcribe directly on the numpy
array, no temp file, no disk write anywhere in the loop -> print the
transcript -> loop back to listening.

Deliberately outside the formal ports/adapters architecture -- a throwaway
script proving the microphone, GPU, and voice libraries actually work
together on this real machine before WP-20 formalizes anything into
WakeWordPort/SttPort and real adapters (see
docs/architecture/m1-voice-architecture.md section 9).

Run with: uv run poc/wp19_04_combined.py
"""

# ruff: noqa: T201, D103 -- disposable script: terminal output and a bare
# main() are the point, not library hygiene.
from __future__ import annotations

import numpy as np
import openwakeword
import sounddevice as sd
from faster_whisper import WhisperModel
from openwakeword.model import Model

SAMPLE_RATE = 16000
WAKEWORD_CHUNK_SAMPLES = 1280  # openWakeWord expects 80ms chunks at 16kHz
DETECTION_THRESHOLD = 0.5
COMMAND_DURATION_S = 5.0
INT16_FULL_SCALE = 32768.0


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
    print("Downloading/verifying openWakeWord pretrained models...")
    openwakeword.utils.download_models()

    print("Loading 'hey_jarvis' wake-word model...")
    wakeword_model = Model(wakeword_models=["hey_jarvis"])

    print("Loading WhisperModel('medium', device='cuda', compute_type='float16')...")
    whisper_model = WhisperModel("medium", device="cuda", compute_type="float16")

    print("Listening for 'hey jarvis'... Ctrl+C to stop.")

    with sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=WAKEWORD_CHUNK_SAMPLES
    ) as stream:
        try:
            while True:
                chunk, _ = stream.read(WAKEWORD_CHUNK_SAMPLES)
                score = _score_for_hey_jarvis(wakeword_model.predict(chunk.reshape(-1)))
                if score < DETECTION_THRESHOLD:
                    continue

                print(f"DETECTED  score={score:.3f} -- listening for command...")
                command_audio = _to_whisper_input(_capture_command_audio(stream))

                segments, _info = whisper_model.transcribe(command_audio, language="en")
                transcript = "".join(segment.text for segment in segments).strip()
                print(f"Transcript: {transcript!r}")
                print("Listening for 'hey jarvis'... Ctrl+C to stop.")
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
