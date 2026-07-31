# ADR-0020: Multi-provider reasoning behind a ReasoningPort abstraction

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Depending on a single reasoning provider is both a single point of failure and a way of silently coupling the entire codebase's business logic to one vendor's API shape.

## Decision

All reasoning providers (ChatGPT, Claude, and others) are accessed exclusively through a single ReasoningPort Protocol; the application layer calls the port, never a provider SDK directly.

## Consequences

Adding or swapping a provider is an adapter-level change, not a domain or application change. The cost is that the ReasoningPort's interface must stay a lowest-common-denominator abstraction general enough for every provider behind it.
