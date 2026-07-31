# ADR-0012: Voice/speaker verification is a convenience filter, not an authorization boundary

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Speaker verification is defeated by replay attacks and, increasingly, by cheap voice cloning; treating a verified voiceprint as proof of identity for authorization purposes would be relying on a control known to be breakable.

## Decision

Voice and speaker verification may be used to personalize behavior or reduce friction, but are never sufficient, alone, to satisfy any policy tier above CONFIRM. They carry no authorization weight in the policy engine.

## Consequences

A cloned or replayed voice cannot escalate a MANUAL_ONLY action to proceed. The cost is that legitimate voice-only workflows are capped at CONFIRM-tier actions; anything more sensitive needs a different authorization channel.
