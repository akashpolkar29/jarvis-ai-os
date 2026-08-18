"""Live diagnostic: wake-word scores from the real OpenWakeWordAdapter, standalone.

Not part of the formal test suite -- a manual diagnostic script, kept
committed (not throwaway) because of what it isolated during M1 live
verification, and what it is still the right tool for. Uses
jarvis.adapters.wake_word.OpenWakeWordAdapter's own real frame source
directly (the exact same code path "jarvis listen" itself uses -- same
model, same threshold, same mic resolution), not a simplified
reimplementation, so what you see here is representative of what's
actually happening inside jarvis's own capture path.

Status as of the M1 live-verification session that created this
script: the bug is narrowed, not fixed. Independent testing with
`pw-record` (PipeWire's own recorder, bypassing this script/jarvis
entirely) confirmed the OS/PipeWire audio layer itself works -- a
restart of the pipewire/pipewire-pulse/wireplumber user services fixed
a stale-graph issue that had made `pw-record` show flat, non-reactive
levels. After that fix, `pw-record` shows real, reactive levels on
real speech. This script, run the same way at the same time, still
shows flat, ambient-level scores with no reaction to speech. That
isolates the remaining bug to jarvis's own audio-capture code
(OpenWakeWordAdapter._default_frame_source's sounddevice.InputStream
usage, or how PortAudio's "default" device resolves) -- not the OS,
not the driver, not PipeWire itself.

Next diagnostic step this script is for: compare exactly which device
sounddevice/PortAudio opens (see sounddevice.query_devices()) against
whatever `pw-record --target <node-id>` targets, at the same moment,
to find where the two diverge.

Prints one "score=0.XXXX" line per captured 80ms frame, continuously,
matching the WP-20 diagnostic pattern. Speak "hey jarvis" (or anything)
while it's running and watch what the numbers do:

  - Scores near 0 the whole time, never moving even when you speak
    loudly close to the mic -> still an audio-capture problem specific
    to this code path (see the status note above).
  - Scores that move and fluctuate with your voice but never approach
    the default threshold (0.5) -> the mic/model pipeline is working,
    but detection sensitivity or wake-phrase pronunciation is the
    issue, not silence.
  - Scores that DO cross 0.5 for two consecutive frames here, when
    jarvis listen itself produces nothing -> the problem is downstream
    of wake-word detection (VAD/STT/intent/dialog), not the mic or the
    wake-word model.

Run with: uv run poc/debug_wp25_live_wake_scores.py
Press Ctrl+C to stop.
"""

# ruff: noqa: T201, D103 -- disposable diagnostic script, not
# library code: terminal output and reaching into the real adapter's
# own frame source (its only per-frame score signal) are the point.
from __future__ import annotations

import asyncio

from jarvis.adapters.wake_word import OpenWakeWordAdapter


async def main() -> None:
    adapter = OpenWakeWordAdapter()
    print("Starting live wake-word scoring against the real adapter.")
    print("Speak now -- watch the numbers. Ctrl+C to stop.\n")

    async for score, _chunk in adapter._default_frame_source():
        print(f"score={score:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
