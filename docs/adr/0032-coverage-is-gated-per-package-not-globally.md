# ADR-0032: Coverage is gated per-package, not globally

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

A single global coverage threshold lets a well-tested, low-risk module (e.g. a CLI argument parser) mathematically compensate for an under-tested, high-risk module (e.g. the policy engine) - the aggregate number can look fine while the part that matters most is barely covered.

## Decision

Coverage gates are configured per-package in CI - starting with src/jarvis/domain and src/jarvis/application/policy - rather than as one repository-wide threshold, so each security-relevant package must earn its own coverage number.

## Consequences

The policy engine's test coverage can never hide behind a well-tested but low-stakes package elsewhere in the tree. The cost is more CI configuration (one coverage report invocation per gated package) than a single global --fail-under line.
