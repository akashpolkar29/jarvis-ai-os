# ADR-0014: SECRET data is DENY to any cloud provider, unconditionally

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

API keys, passwords, and tokens are catastrophic if they leak, and any "except in this case" exception to a cloud-egress rule for SECRET data becomes the case an attacker (or a confused prompt) targets.

## Decision

Data classified SECRET is DENY for egress to any cloud reasoning provider, with no exception path, no override, and no code path that places it into a model's context window.

## Consequences

Some workflows (e.g. "help me debug this API call") must be restructured so the secret itself never enters the payload sent to a reasoning provider, even redacted. This is treated as an acceptable UX cost given what SECRET data represents.
