# ADR-0021: No vendor names in domain, application, or ports

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Vendor-specific naming ("the ChatGPT handler," "an Anthropic-specific retry") leaks implementation detail into layers that are supposed to be implementation-agnostic, and makes it obvious, on sight, when someone has bypassed the port abstraction.

## Decision

The strings "openai", "anthropic", "chatgpt", "claude", and "gpt" (and future vendor names) may never appear in src/jarvis/domain, application, or ports. This is enforced by static grep as well as review.

## Consequences

A reviewer or a simple grep can catch an abstraction leak immediately. The cost is occasional awkward generic naming ("provider A" style comments) when discussing provider-specific quirks that do belong in a code comment at the adapter layer.
