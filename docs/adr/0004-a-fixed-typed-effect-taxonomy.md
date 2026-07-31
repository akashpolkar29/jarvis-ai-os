# ADR-0004: A fixed, typed effect taxonomy

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Without a closed, shared vocabulary of effects, each capability author would invent their own notion of "risky," making it impossible for one policy engine to reason about all of them consistently.

## Decision

Effects are drawn from a single closed enumeration - READ_LOCAL, WRITE_LOCAL, DESTRUCTIVE, IRREVERSIBLE, CREDENTIAL, EGRESS_SENSITIVE (extended over time via ADR, never ad hoc) - and every capability declares the full set of effects it can produce.

## Consequences

The policy engine can be exhaustive and simple. Extending the taxonomy is a deliberate, reviewed act (a new ADR), not a side effect of adding a capability, which is friction by design.
