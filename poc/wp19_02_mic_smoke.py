# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "sounddevice",
#     "numpy",
# ]
# ///
"""WP-19 stage 2: microphone capture smoke test.

Proves real audio can be captured from this machine's default input device
before wake-word/STT complexity is layered on top. Captures as int16 (the
format openWakeWord expects in stages 3/4) so later stages reuse this exact
capture path unchanged.

Nothing captured here is ever written to disk, even temporarily -- kept in
the spirit of ADR-0018 even though this script sits outside its formal
enforcement (see docs/architecture/m1-voice-architecture.md section 9).

Run with: uv run poc/wp19_02_mic_smoke.py
"""

# ruff: noqa: T201, D103 -- disposable script: terminal output and a bare
# main() are the point, not library hygiene.
from __future__ import annotations

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CAPTURE_DURATION_S = 3.0
INT16_FULL_SCALE = 32768


def main() -> None:
    print("Input devices:")
    print(sd.query_devices())

    default_input = sd.query_devices(kind="input")
    print(f"\nUsing default input device: {default_input['name']!r}")

    print(f"Recording {CAPTURE_DURATION_S:.0f}s at {SAMPLE_RATE}Hz mono (int16)...")
    audio = sd.rec(
        int(CAPTURE_DURATION_S * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
    )
    sd.wait()

    samples = audio.reshape(-1)
    peak = int(np.abs(samples).max())
    print(f"Captured {samples.size} samples.")
    fraction = peak / INT16_FULL_SCALE
    print(f"Peak amplitude: {peak} / {INT16_FULL_SCALE} ({fraction:.1%} of full scale)")

    if peak == 0:
        print("WARNING: peak amplitude is zero -- captured buffer is pure silence.")
    elif peak >= INT16_FULL_SCALE - 1:
        print("WARNING: peak amplitude at/near full scale -- signal may be clipping.")
    else:
        print("Signal captured successfully.")


if __name__ == "__main__":
    main()
