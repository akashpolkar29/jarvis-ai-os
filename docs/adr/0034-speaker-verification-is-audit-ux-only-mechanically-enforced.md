# ADR-0034: Speaker verification is audit/UX only, mechanically enforced

## Status

Accepted

## Date

2026-08-15

## Source

Work package WP-23 implementation (SpeakerIdPort + stub adapter), operationalizing ADR-0012 for real code

## Context

ADR-0012 established the principle: voice/speaker verification is a convenience filter, never an authorization boundary. M1 is the first point this principle has to survive contact with real code, under real time pressure, rather than staying a paper rule. The M1 architecture doc named the concrete risk directly: it would be easy, and would feel reasonable, to write something like `if speaker_match: physical_confirmation_available = True`. That single line would silently violate ADR-0012 and let a good enough voice clone or a recording of the real user satisfy MANUAL_ONLY.

A comment or code-review convention is not a strong enough guarantee against that -- it can be missed once, under pressure, by anyone (including a future version of the assistant building this project), and the mistake would not announce itself; it would just quietly work, most of the time, until a replay attack found it.

## Decision

Two things, together, make this a mechanically enforced guarantee rather than a comment:

1. `SpeakerIdPort.score(audio: Segment) -> SpeakerScore` is a synchronous, non-authoritative signal port. `UnverifiedSpeakerIdAdapter`, its only implementation as of M1, always returns `SpeakerScore(verified=False, confidence=0.0)` -- a deliberate stub, not a placeholder for unfinished work: building a real speaker-embedding/enrollment model is explicitly deferred, since this output is non-authoritative by design and nothing yet consumes it for anything but audit logging and UX tone.
2. `tests/meta/test_speaker_id_isolation.py` makes the ADR-0012 rule structurally checkable: it AST-scans every non-`__init__.py` source file under `src/jarvis` for code that references both `PolicyContext`-related identifiers and `SpeakerScore`/`SpeakerIdPort`-related identifiers together, plus a field-shape check confirming `PolicyContext` still has exactly its two known-safe boolean fields, plus a proof that the scan predicate itself actually fires against a deliberately crafted violation (not just that today's tree happens to be clean). `__init__.py` barrel files are deliberately excluded -- they legitimately re-export both vocabularies together as aggregation, not construction, and the isolation test proves this distinction is real, not just asserted.

`kernel.voice_loop.run_voice_loop` (WP-25) calls `speaker_id.score()` once per utterance and only logs the result (`_logger.info(...)`) -- it is never read again, never passed to anything that constructs a `PolicyContext`, and the isolation test verifies this holds for that file exactly as it does for every other.

## Consequences

Anyone saying the wake phrase wakes the system and can attempt any command; only physical confirmation (ADR-0013, ADR-0035) can grant a CONFIRM/MANUAL_ONLY-tier one. A real speaker-verification model, if built later, changes only logging/UX behavior -- it cannot become an authorization input without first breaking `test_speaker_id_isolation.py`, which is the point: the guarantee is enforced by the test suite itself, not by developer discipline alone.
