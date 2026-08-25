# ADR-0052: No real-time indicator for memory recall

## Status

Proposed

## Date

2026-08-25

## Source

M4 scoping question 4 (`docs/architecture/m4-scoping-notes.md`),
answered directly by the user 2026-08-25: "No indicator for memory
recall. ADR-0047's indicator exists because a synthetic keystroke is
an irreversible, externally-visible action the instant it fires --
recall doesn't share that property... Reserve real-time indicators for
actions with real-world side effects, not memory reads." A draft for
the user's own review, not a decision made unilaterally here.

## Context

`docs/ROADMAP.md`'s own "always legible" standing principle requires
every JARVIS action be legible to the user in real time, spoken and/or
shown. ADR-0047 built this project's first real, concrete instance of
what that looks like when a capability's own safety story depends on
it: a dedicated visual profile plus a spoken announcement, gating a
hard-abort precondition, specifically because a synthetic keystroke
fired into the wrong window is an irreversible, externally-visible
action the instant it happens -- the indicator exists to give a
physically-present human a real, in-the-moment chance to notice and
abort *before* an unrecoverable action completes.

`RetrievalPort.retrieve()` (ADR-0048) shares none of that shape: it
reads, it does not act; a wrong or stale recall changes what JARVIS
says next, which the user hears and can correct in the same
conversation turn, the same way a human corrects someone who
misremembered something -- there is no equivalent "already happened,
cannot be undone" moment recall shares with a keystroke.

## Decision

**No real-time visual or audible indicator is built for memory
recall in this milestone.** `RetrievalPort.retrieve()` remains a
plain, silent read from `AuthorizationOrchestrator`'s own perspective
-- no new indicator mechanism, no reuse of ADR-0047's own
`adapters/terminal_profile.py`-style machinery, no new `TtsPort`
announcement wired specifically to recall.

**This is a real, considered scope boundary on "always legible," not a
quiet exception to it.** `docs/ROADMAP.md`'s principle itself already
states plainly that "what actually gets spoken vs. shown... remains
deliberately undecided" and is a "decided product expectation, not a
specific UI or output design" -- this ADR's own reading, stated
explicitly rather than assumed: real-time indicators are the right
tool specifically for actions carrying real, external, hard-to-reverse
consequences (ADR-0047's own keystroke case); a silent, correctable
read is legible enough through the conversation itself (the user
already hears what JARVIS recalled, embedded in its own response) --
"legible" does not require "flagged with a dedicated signal" for every
single action uniformly, or ADR-0047's own indicator would need to be
duplicated for every `READ_LOCAL`/`ALLOW` capability in this repo,
which this project has never done and this ADR does not start doing
here.

## Consequences

Memory recall stays a comparatively low-friction, low-latency
operation -- no synthesis/playback step blocking a response the way
ADR-0047's own hard-abort precondition (real-time indicator) does
before Terminal ever sends a keystroke. This is a real, deliberate
trade this ADR makes explicitly, not an oversight: recall happening
fast and silently is the whole point of the "conversationally
self-correcting" reasoning above.

**Originally left as an explicit open question this ADR did not
resolve, now answered elsewhere**: whether a memory *write* succeeding
deserves its own legibility signal -- a write is not read-only the way
recall is; something durable now exists that didn't before, arguably
closer in kind to a real, consequential action than a read is. This
ADR's own scope was, and remains, recall specifically, per the scoping
question it answers -- it does not extend its own reasoning to cover
write by implication, and still does not. **Resolved by ADR-0053**
(drafted after this ADR, not a revision of it): also no dedicated
indicator, but for write-specific reasons (reversibility via ADR-0051's
retention mechanics; extending `kernel/voice_loop.py`'s existing
response-announcement dispatch) independent of this ADR's own
recall-specific reasoning above -- two separately-reasoned answers
that happen to agree, not one conclusion stretched to cover both.

**Not foreclosed, if the user's own answer changes later**: nothing
here prevents a future milestone or ADR from adding a recall indicator
if real use reveals users are meaningfully confused by silent recall
in practice -- this ADR states the reasoning for the current decision,
not a permanent, unrevisitable rule the way ADR-0046's own "no other
capability may cite Terminal as precedent" is a hard boundary. Should
this need revisiting, that is a fresh, explicit decision, not implied
by anything in this document.
