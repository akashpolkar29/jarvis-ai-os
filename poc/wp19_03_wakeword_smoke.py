# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "openwakeword",
#     "sounddevice",
#     "numpy",
# ]
# ///
"""WP-19 stage 3: openWakeWord smoke test on live microphone audio.

Streams real mic audio through openWakeWord's pretrained "hey_jarvis" model
and prints its detection score, so triggering on an actual spoken "hey
jarvis" (and not false-triggering on ambient room noise) can be confirmed
by ear/eye before wiring anything else on top (see
docs/architecture/m1-voice-architecture.md section 9).

Nothing is written to disk. Run until Ctrl+C.

Run with: uv run poc/wp19_03_wakeword_smoke.py
"""

# ruff: noqa: T201, D103, TID251 -- disposable script: terminal output, a
# bare main(), and wall-clock time.monotonic() for a print-rate throttle
# are the point here, not library hygiene or ClockPort injection.
from __future__ import annotations

import time

import openwakeword
import sounddevice as sd
from openwakeword.model import Model

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280  # openWakeWord expects 80ms chunks at 16kHz
DETECTION_THRESHOLD = 0.5
SCORE_PRINT_INTERVAL_S = 0.5


def _score_for_hey_jarvis(predictions: dict[str, float]) -> float:
    for key, score in predictions.items():
        if "hey_jarvis" in key.lower():
            return score
    return 0.0


def main() -> None:
    print("Downloading/verifying openWakeWord pretrained models...")
    openwakeword.utils.download_models()

    print("Loading 'hey_jarvis' model...")
    model = Model(wakeword_models=["hey_jarvis"])

    print(f"Listening for 'hey jarvis' (threshold={DETECTION_THRESHOLD})... Ctrl+C to stop.")
    last_print = 0.0

    with sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=CHUNK_SAMPLES
    ) as stream:
        try:
            while True:
                chunk, _ = stream.read(CHUNK_SAMPLES)
                score = _score_for_hey_jarvis(model.predict(chunk.reshape(-1)))

                now = time.monotonic()
                if score >= DETECTION_THRESHOLD:
                    print(f"DETECTED  score={score:.3f}")
                elif now - last_print >= SCORE_PRINT_INTERVAL_S:
                    print(f"score={score:.3f}")
                    last_print = now
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
