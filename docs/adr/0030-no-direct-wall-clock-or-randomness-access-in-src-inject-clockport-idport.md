# ADR-0030: No direct wall-clock or randomness access in src/: inject ClockPort/IdPort

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Code that calls datetime.now(), time.time(), or uuid.uuid4() directly is non-deterministic and untestable without monkeypatching, and a hash-chained audit log with untraceable timestamps loses much of its forensic value.

## Decision

No file under src/ calls datetime.now()/utcnow(), time.time()/monotonic(), or uuid.uuid1()/uuid4() directly. Anything needing the current time or a fresh identifier takes a ClockPort or IdPort dependency instead. This is enforced twice: a ruff banned-api rule for direct imports, and an AST-based meta-test that also catches bare `import time; time.time()`-style attribute calls ruff's rule can't see.

## Consequences

Tests can inject a fixed clock/id source and get fully deterministic, reproducible output - including reproducible audit log entries. The cost is an extra constructor parameter (or two) threaded through anything that currently reaches for the wall clock casually.
