# ADR-0013: Physical interaction with the machine is the real authorization boundary

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Given that voice cannot serve as an authorization boundary, the system needs some notion of "the user is actually here and actually intends this" for MANUAL_ONLY-tier actions.

## Decision

MANUAL_ONLY tier is satisfied only by physical interaction with the machine itself (e.g. an on-device confirmation, not a remote or voice channel) - this is the one authorization signal the design treats as trustworthy.

## Consequences

Remote-only or voice-only deployments cannot fully exercise MANUAL_ONLY-tier capabilities, which is an intentional limitation rather than a gap to be closed later. Physical presence detection itself is out of scope for Milestone 0 and will need its own ADR when implemented.
