# ADR-0024: A reviewing model must produce a failing test, not a verdict

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Asking a second model "does this look right?" produces an opinion that is easy to rubber-stamp, hard to verify, and doesn't compose with the project's actual test suite.

## Decision

When a reasoning provider is used to review another provider's candidate, its output must be a concrete, executable failing test case demonstrating the problem - never a prose verdict, score, or opinion with no way to confirm it's grounded in the actual code.

## Consequences

A review either produces a real, addable regression test or it produces nothing actionable - there's no middle ground where an unfounded "this looks wrong" opinion blocks a candidate. The cost is that subtle stylistic or design concerns that don't manifest as a failing test go unflagged by this mechanism.
