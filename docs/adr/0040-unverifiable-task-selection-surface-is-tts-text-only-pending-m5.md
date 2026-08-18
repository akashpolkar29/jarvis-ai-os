# ADR-0040: Unverifiable-task selection surface is TTS/text-only pending M5's Console UI

## Status

Accepted

## Date

2026-08-18

## Source

Work package WP-29 planning finding (M2 reasoning-layer reconciliation, per `docs/architecture/m2-reasoning-layer.md` and the WP-28 planning pass)

## Context

`docs/architecture/m2-reasoning-layer.md` section 5 (deliverable #7) names an "unverifiable-task regime: parallel heterogeneous drafting + user selection UI (escalation OFF by default here)." No such UI exists anywhere in this repo — `m5-browser-coding.md` is still a gate-only placeholder, and its own "Deliberately deferred, not an oversight" section quotes the recovered design conversation directly: *"Console UI views. Interface frozen; views deliberately not. You will know what you want after six months of using the HUD."*

`docs/ROADMAP.md`'s "Standing principle: always legible" states: *"Every action JARVIS takes, across every milestone, should be legible to Akash in real time — both spoken (reusing M1's existing TTS output) and visible on-screen (via M5's Console UI, once it exists)... Nothing about this principle authorizes designing M5's Console UI or M6's integrations ahead of their own planning passes — it only states that when they are designed, silent/invisible operation is not an acceptable outcome."*

Building deliverable #7's "user selection UI" now would mean designing M5's Console UI ahead of M5's own planning pass — exactly what the rolling-wave principle and M5's own placeholder doc argue against, and exactly the kind of pre-written detail that has already gone stale once in this project (`m1-voice-architecture.md`, corrected in `bde285d`).

## Decision

M2 builds deliverable #7's selection *logic* only — the parallel heterogeneous drafting and the escalation-off gating for unverifiable tasks. The actual surface a candidate selection is presented through stays TTS/text via the existing interaction layer (M1's `TtsPort` and stdout/CLI text) until M5 builds a real Console UI. The boundary between M2's selection logic and whatever surfaces it is port-shaped (a to-be-named presentation port, designed in M2's own port layer alongside `ReasoningPort`/`ValidationPort`), so M5 can supply a real Console UI implementation later without M2's logic changing at all. TTS/text assumptions are not hardcoded into the selection logic itself.

## Consequences

M2 satisfies the "always legible" principle today, with the mechanisms that already exist, rather than either building UI ahead of its milestone or leaving unverifiable-task selection silent in the meantime (which the standing principle rules out as an acceptable outcome). The cost is one more port to design carefully in M2 — its shape now determines how easy or hard M5's eventual Console UI integration will be, so it needs the same care as `ReasoningPort` itself, not treated as an afterthought.

This does not authorize any Console UI design work in M2 or in `m5-browser-coding.md` — M5's own placeholder status is unchanged by this ADR.
