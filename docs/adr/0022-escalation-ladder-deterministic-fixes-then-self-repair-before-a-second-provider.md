# ADR-0022: Escalation ladder: deterministic fixes, then self-repair, before a second provider

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Consulting a second, more expensive reasoning provider every time something fails is slow and costly, and often unnecessary when the failure is something a deterministic tool (a linter, a formatter, a type checker) could have fixed directly.

## Decision

When a candidate fails validation, the system first attempts cheap deterministic fixes (auto-formatting, straightforward lint auto-fixes), then attempts self-repair with the same provider that produced the candidate, and only escalates to a second provider if both of those fail.

## Consequences

Most transient failures are resolved without ever invoking a second, more expensive provider call. The cost is a small amount of added latency for genuinely hard failures, which must climb the full ladder before getting a second opinion.
