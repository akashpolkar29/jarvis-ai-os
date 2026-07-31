# ADR-0008: Provenance trust dimension: USER_DIRECT / SYSTEM / UNTRUSTED_EXTERNAL

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Not all input to the system is equally trustworthy - a value typed directly by the user, a value produced by JARVIS's own internals, and a value scraped from a web page or received in an email all carry different risk, but a naive implementation treats them as interchangeable strings once they're in memory.

## Decision

Every value that crosses a boundary is tagged with a trust level - USER_DIRECT, SYSTEM, or UNTRUSTED_EXTERNAL - as part of its provenance, tracked through the domain model rather than inferred ad hoc at each use site.

## Consequences

Downstream logic (especially the policy engine) can make trust-sensitive decisions without re-deriving where a value came from. The cost is that every boundary-crossing adapter must correctly assign a trust level at the point of ingestion - an omission there is a silent trust-downgrade bug.
