# ADR-0029: domain/ is stdlib-only, with no I/O and no async

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

If the domain model can perform I/O or await anything, its behavior becomes dependent on the environment it runs in, and testing it requires mocking that environment rather than just calling pure functions.

## Decision

Everything under src/jarvis/domain imports the standard library only, performs no I/O, and defines no async functions. import-linter's C2 contract and an AST-based meta-test both enforce this at CI time.

## Consequences

The domain model can be tested with plain synchronous unit tests and no fixtures beyond input data. The cost is that anything domain code needs from the outside world (the time, a fresh id, a file's contents) must be passed in by the caller rather than fetched directly.
