# ADR-0018: Audio is never persisted to disk

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Recorded audio of a user's voice is uniquely sensitive (it's both PII and a biometric), and any code path that writes it to disk "just for debugging" tends to leave debug artifacts lying around in production.

## Decision

Audio data is never written to disk under normal operation. The only exception is an explicit, temporary, clearly-labeled debug mode that must be deliberately enabled - it is never the default and never silently persists across a session.

## Consequences

Debugging audio-related issues without the debug mode enabled means debugging blind on that dimension, by design. Anyone enabling the debug mode is explicitly opting into a temporary reduction in the audio privacy guarantee, and it should be logged.
