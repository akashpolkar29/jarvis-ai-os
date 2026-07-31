# ADR-0001: Ports-and-adapters layered architecture

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

JARVIS mixes untrusted external input, credentials, and destructive local actions in one process; without an enforced boundary, business rules end up entangled with whichever library or vendor SDK happened to be convenient at the time, making privacy and safety guarantees unverifiable by inspection.

## Decision

Adopt Clean Architecture / ports-and-adapters with a strict inward dependency rule: domain -> ports -> application -> adapters -> kernel -> ipc/cli. Each ring may depend only on rings before it in that list; import-linter contracts enforce this at CI time, not just in review.

## Consequences

Business rules (capabilities, effects, policy, provenance) can be reasoned about and tested without a running adapter, database, or network. The cost is boilerplate: every new integration needs a port defined before an adapter can implement it, and the layering must be re-verified (via import-linter) every time a new package is added.
