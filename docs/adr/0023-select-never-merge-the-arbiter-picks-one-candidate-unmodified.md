# ADR-0023: Select, never merge: the arbiter picks one candidate unmodified

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Splicing together pieces of two different candidate implementations (e.g. one model's function body with another's error handling) produces code that neither model actually reasoned about as a whole, and combines two sets of untested assumptions into something new and untested.

## Decision

When multiple reasoning providers produce candidate implementations, the arbiter selects exactly one candidate to use, completely unmodified. It never merges, splices, or otherwise combines pieces of multiple candidates.

## Consequences

Whatever ships has been reasoned about, in full, by at least one model and validated as a whole. The cost is that a good idea in a rejected candidate is simply lost for that round, rather than cherry-picked in.
