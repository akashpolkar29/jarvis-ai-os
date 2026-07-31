# ADR-0019: Destructive/irreversible/credential actions always require MANUAL_ONLY

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Even a well-calibrated policy engine could, through some combination of misconfiguration or clever framing, resolve a genuinely destructive action to CONFIRM instead of the stricter tier it deserves.

## Decision

Any capability whose declared effects include DESTRUCTIVE, IRREVERSIBLE, or CREDENTIAL is hard-pinned to MANUAL_ONLY tier - this floor is not something tier-resolution logic can compute its way around, and it is never satisfiable by voice alone (per the voice-is-not-authorization ADR).

## Consequences

There is one more layer of protection against a policy-engine bug turning a destructive action loose unattended. The cost is that these actions are always maximally inconvenient by design - there is no "trusted enough" path around this floor.
