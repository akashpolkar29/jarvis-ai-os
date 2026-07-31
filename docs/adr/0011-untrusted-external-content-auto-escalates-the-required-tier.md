# ADR-0011: Untrusted external content auto-escalates the required tier

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Content originating outside the user's direct control - a web page, an email body, a README fetched from the internet - can contain instructions aimed at the agent itself (prompt injection), and treating it as equivalent to a direct user instruction is the single most common way such systems get compromised.

## Decision

Any value whose trust level is UNTRUSTED_EXTERNAL automatically raises the minimum policy tier required for any capability invocation it influences, regardless of what that capability would otherwise require.

## Consequences

A prompt-injection payload embedded in fetched content cannot, by itself, unlock a MANUAL_ONLY-tier action at ALLOW. The cost is more CONFIRM/MANUAL_ONLY friction whenever the agent is working with fetched external content, even when the content turns out to be benign.
