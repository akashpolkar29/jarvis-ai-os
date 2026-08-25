# ADR-0053: No dedicated real-time indicator for memory write either, for a different reason than recall

## Status

Accepted

**Acceptance note (2026-08-26):** accepted by the user directly, authorizing full M4 implementation (WP-57 through WP-64) in the same overnight pass. Accepted as drafted -- no changes to this ADR's own Decision were made as part of acceptance.

## Date

2026-08-25

## Source

The open question ADR-0052 itself named but explicitly declined to
answer: "whether a memory *write* succeeding deserves its own
legibility signal (distinct from decision 4's recall-specific
answer)... A future ADR (or a revision of this one) is the right
place to settle that." This is that future ADR, not a revision of
ADR-0052 -- write and recall get independently reasoned answers, not
one conclusion stretched to cover both. A draft for the user's own
review, not a decision made unilaterally here.

## Context

ADR-0052 concluded no indicator is needed for memory *recall*, on
grounds specific to reads: a bad recall changes what JARVIS says,
which the user hears and corrects in conversation, the same way one
corrects someone who misremembered something -- there is no
"already happened, cannot be undone" moment a read shares with
ADR-0047's own keystroke case.

A memory *write* is not a read, and does not share recall's own
reasoning by default: something durable now exists that didn't
before, a real, lasting side effect a bad recall does not have. Taken
at face value, this looks closer to the kind of "real-world
consequence" ADR-0047's indicator exists for than recall does --
worth its own, separate reasoning pass, not assumed to inherit
ADR-0052's answer.

## Decision

**Still no dedicated, ADR-0047-shaped real-time indicator for memory
write -- but for a different, write-specific reason, not recall's
reason.** Two real properties distinguish a memory write from ADR-0047's
keystroke case, checked directly against what this milestone has
already decided elsewhere in this same drafting pass, not assumed:

1. **A memory write is reversible; a fired keystroke is not.** ADR-0047's
   indicator exists specifically because a synthetic keystroke is
   irreversible the instant it lands -- the whole point of the
   indicator is giving a human a real chance to notice and abort
   *before* that irreversible moment. A memory write has a real,
   already-decided undo path: ADR-0051's own TTL/pinning mechanism
   means an unwanted memory does not persist forever by default, and
   (per ADR-0051's own "Also real, also open" note) an explicit
   "forget X" capability is a real, plausible future addition. An
   action with a real undo path does not carry the same
   once-it-fires-it's-permanent urgency a real-time indicator exists
   to protect against.
2. **This project already has a real, general response-announcement
   *pattern* -- not an automatic mechanism every capability gets for
   free, checked directly before asserting this -- and extending it is
   the right-sized fix, not a new indicator subsystem.**
   `kernel/voice_loop.py`'s own `_speak(tts, play_fn, response_text)`
   call does announce a capability's outcome back to the user via
   `TtsPort`, but `response_text` comes from `_authorize_and_execute`,
   which is a **closed, hardcoded dispatch over exactly three cases
   today** (`PING_CAPABILITY_ID`, `READ_FILE_CAPABILITY_ID`, and music
   commands) -- not a generic hook new capabilities join automatically.
   A memory-write capability would need the same small, ordinary kind
   of addition every one of those three already needed: one new
   branch, returning a real `_describe`-shaped response string. That
   is real, necessary work for the implementing work package, not
   something this milestone gets free -- but it is the same shape of
   small addition already-existing capabilities all needed, not a new
   architectural mechanism the way ADR-0047's indicator was. That
   distinction -- "extend an existing, ordinary dispatch" vs. "build a
   new, dedicated subsystem" -- is the real reason a second indicator
   isn't warranted, not an (incorrect) assumption that announcement
   already happens automatically.

**This is not "memory write is unimportant," and does not weaken
ADR-0049's own DENY guarantee or any other decision in this
document** -- it is specifically a decision about whether a *second*,
dedicated, ADR-0047-style mechanism is warranted on top of what
`kernel/voice_loop.py` already provides, and the answer is no, because
the two real properties above (reversible; already announced) are both
true and both absent from ADR-0047's own keystroke case.

## Consequences

`kernel/memory.py`'s composition root needs no new indicator
subsystem. It does need one new, ordinary branch in
`kernel/voice_loop.py`'s own `_authorize_and_execute` dispatch (real,
necessary work for the implementing work package, named here so it
isn't discovered as a surprise mid-implementation) -- the same kind of
small addition `PING_CAPABILITY_ID`/`READ_FILE_CAPABILITY_ID`/each
music command already required, not a new architectural mechanism
this ADR needs to design further.

**Real, explicitly-named limit of this decision**: it assumes a memory
write reached through `kernel/voice_loop.py`'s own real flow, where
the existing announcement mechanism actually fires. If a future work
package ever adds a way to write to memory *outside* that flow (a
CLI-only path with no voice loop involved, for instance -- not
proposed anywhere in this document, but not structurally impossible
either), this ADR's second reason no longer applies there, and that
path would need its own, fresh legibility decision -- not assumed
covered by this ADR's own reasoning, which is scoped to the real flow
this milestone actually builds.

**Not foreclosed, matching ADR-0052's own closing note**: if real use
reveals users are meaningfully confused about what got memorized
despite the existing spoken announcement (e.g., a long or noisy
announcement that doesn't clearly communicate "this is now
permanently stored"), revisiting this with a fresh, explicit decision
remains open -- this ADR states the reasoning for the current
decision, not a permanent rule.
