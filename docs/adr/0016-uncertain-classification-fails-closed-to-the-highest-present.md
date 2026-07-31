# ADR-0016: Uncertain classification fails closed to the highest present

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

When a task mixes inputs of different classifications, or an adapter can't determine an input's classification with confidence, defaulting to the lowest (most permissive) classification is a silent privacy leak waiting to happen.

## Decision

Whenever a task's overall classification is uncertain or its inputs are mixed, the task inherits the highest classification present among them - never a lower, more permissive default.

## Consequences

The system is conservative by construction: some PUBLIC-only tasks that happen to touch one misclassified or ambiguous input will be treated more restrictively than strictly necessary. This is accepted; the alternative failure mode (leaking SECRET/SENSITIVE data because of an optimistic default) is categorically worse.
