# ADR-0015: SENSITIVE data requires explicit CONFIRM before reaching a cloud provider

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Personal information and third-party confidential data are not as catastrophic as secrets if leaked, but still carry real cost, and silently routing them to a cloud API on the agent's own initiative removes the user's ability to make that call.

## Decision

Data classified SENSITIVE may be sent to a cloud reasoning provider, but only behind an explicit CONFIRM-tier user acknowledgment at the point of egress; it is never sent by default.

## Consequences

Every code path that could route SENSITIVE data off-device must be instrumented to trigger a CONFIRM rather than silently proceeding - this is a real integration burden on every adapter, not just a documentation note.
