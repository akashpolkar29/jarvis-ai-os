# ADR-0006: Four-tier policy model: ALLOW / CONFIRM / MANUAL_ONLY / DENY

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

A binary allow/deny model can't express "this is fine unattended" vs "this needs the user to look at it" vs "this needs the user's hands on the keyboard," which are three meaningfully different postures for an autonomous agent.

## Decision

The policy engine resolves every capability invocation to exactly one of four tiers: ALLOW (proceeds unattended), CONFIRM (needs an acknowledgment), MANUAL_ONLY (needs the user to physically perform or explicitly authorize the step), or DENY.

## Consequences

UI and audit logic can be written once against four well-defined outcomes. Adding a fifth tier later is a breaking change to every piece of code that pattern-matches on this enum, so the tier set itself is not expected to grow casually.
