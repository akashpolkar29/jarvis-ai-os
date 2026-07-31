# ADR-0002: Capabilities, not agents, as the kernel's unit of extension

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

A system that grows by adding named "agents" (an email agent, a calendar agent) tends to accrete integration-specific logic into the kernel itself, and each new agent becomes another place that needs its own security review.

## Decision

The kernel knows only about capabilities - declared units of effect-bearing behavior - never about specific agents or integrations. New functionality is added as a plugin behind jarvis.plugin_api; nothing in domain, application, or ports names a specific integration.

## Consequences

The kernel's trusted computing base stays fixed in size as functionality grows; a plugin vulnerability is contained to what its declared capabilities allow. The cost is that every capability must be modeled generically enough to fit the effect/tier vocabulary, which is more design work up front than a bespoke integration.
