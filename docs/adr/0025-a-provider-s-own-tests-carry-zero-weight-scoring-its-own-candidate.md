# ADR-0025: A provider's own tests carry zero weight scoring its own candidate

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

A model grading its own candidate against tests it also wrote can trivially write tests that its candidate happens to pass, which would make the validation step circular and worthless as a check.

## Decision

When scoring a candidate, any test authored by the same provider that produced that candidate carries zero weight in that candidate's score - only tests from the existing suite, from a different provider, or from the human author actually count.

## Consequences

A provider cannot game its own evaluation by writing lenient self-tests. The cost is that a genuinely good test written by a provider about its own candidate needs to be independently proposed (e.g. adopted into the permanent suite by a human) before it counts for anything.
