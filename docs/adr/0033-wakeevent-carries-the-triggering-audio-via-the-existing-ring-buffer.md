# ADR-0033: WakeEvent carries the triggering audio, via the existing ring buffer

## Status

Accepted

## Date

2026-08-15

## Source

Work package WP-25 implementation finding (kernel/voice_loop.py wiring, per docs/architecture/m1-voice-architecture.md)

## Context

`WakeWordPort.stream()` (WP-20) yields `WakeEvent(score: float)` only --
no audio. `VadPort.segment(audio: AudioChunk)` (WP-21) needs actual
captured audio to operate on. The M1 architecture doc's pipeline
(section 2) draws a ring buffer feeding both wake-word detection and,
implicitly, VAD immediately after a trigger -- but neither port's
actual signature, as built and frozen in WP-20/WP-21, provides any
mechanism for audio to flow from the wake-word adapter to VAD.
`WakeWordPort`/`VadPort` are each individually correct and already
merged; the connection *between* them that the doc's pipeline diagram
implies was simply never built.

`OpenWakeWordAdapter` already constructs a private `_AudioRingBuffer`
internally (WP-20) and pushes every captured frame into it -- but its
`snapshot()` method is never called anywhere in the real code path.
This looks like exactly the seam this gap needs, apparently anticipated
by WP-20 but never wired up to anything.

Four options were considered:

1. **Extend `WakeEvent`/`WakeWordPort` to carry the triggering audio.**
2. **Add a new, seventh port** exposing the ring buffer directly.
   Rejected: the M1 doc's section 4 lists exactly six ports as this
   milestone's full, approved port surface; adding one not in that
   list is itself an unapproved architecture change. The audio handoff
   is also really the wake-word adapter's own internal concern, not a
   distinct capability that warrants its own abstraction boundary.
3. **`kernel/voice_loop.py` opens an independent `sounddevice` capture**
   in parallel to `WakeWordPort`'s internal one. Rejected: two
   independent reads of the same physical microphone have no
   guaranteed sample-level synchronization, risk device/PipeWire
   contention (this project already hit real, hard-to-diagnose
   default-input-device drift during WP-19 and the WP-21 mic
   verification session), and duplicate hardware-access logic
   `OpenWakeWordAdapter` already encapsulates -- exactly the "quietly
   patch around a gap instead of fixing the actual seam" outcome
   CLAUDE.md's hard rule warns against.
4. **Capture a fresh, independent short clip only after the trigger**,
   discarding the ring buffer's pre-trigger content entirely. Rejected:
   cheaper to implement, but a real UX regression -- a user who speaks
   the command in the same breath as the wake phrase ("hey jarvis,
   play music") would lose the "play music" part if it lands before a
   freshly-started capture begins.

## Decision

`WakeEvent` gains a required `audio: AudioChunk` field. `WakeWordPort`'s
contract is unchanged in shape (still `stream() -> AsyncIterator[WakeEvent]`)
but each yielded event now carries real audio, not just a score.

`OpenWakeWordAdapter`'s real implementation is restructured so its
existing ring buffer (built in WP-20, previously write-only) is
actually used: on a confirmed detection, the ring buffer's current
snapshot (the pre-trigger context, unchanged 5.0s window) is combined
with a further, fixed-duration capture continued from the *same*
already-open audio stream (3.0s, chosen as a reasonable default long
enough for a short spoken command and not empirically tuned against
real speech -- a candidate for adjustment once WP-25/26 give a live
testbed) into one `AudioChunk`, attached to the yielded `WakeEvent`.
No new port. No second, independent microphone capture.

## Consequences

`WakeEvent` becomes a slightly heavier contract (an event now always
carries real audio, not just a score), but VAD's audio source stays
connected to the single live stream `WakeWordPort` already owns,
avoiding the sync/contention risk option 3 would have introduced.

The fixed 3.0s post-trigger capture window delays each `WakeEvent`'s
yield by that same duration relative to the acoustic trigger moment --
a real, deliberate latency cost paid once per invocation, not per
frame. This value is a considered default, not a measured one; tuning
it against real usage is legitimate future work once the voice loop
has a live testbed (WP-25/26), not something to re-derive from
scratch.

WP-20's existing tests (`tests/unit/test_wake_word_adapter.py`,
`tests/unit/test_wake_word.py`) required real updates to keep matching
this changed shape, not just new tests layered on top -- done in the
same commit as this ADR, with the full suite re-verified green
afterward, not left inconsistent.
