# ADR-0005: A single policy engine as the sole authorization choke point

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

If authorization checks are scattered across capability implementations, a single missed check anywhere in the codebase is a security hole, and no amount of code review can guarantee there isn't one.

## Decision

Exactly one policy engine (application/policy) evaluates a capability's declared effects, the tier, and the provenance of the data involved, at exactly one point in the call path before any capability executes.

## Consequences

A security review of authorization logic means reading one module, not auditing every capability implementation. The cost is a small amount of indirection: capabilities cannot "just check something quickly" themselves - every check goes through the engine.
