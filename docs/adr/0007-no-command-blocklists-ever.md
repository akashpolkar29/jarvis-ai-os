# ADR-0007: No command blocklists, ever

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Blocklists (banned commands, banned strings) are a well-known losing pattern in security: the attacker (or an adversarially-prompted model) only needs to find one encoding the blocklist author didn't think of.

## Decision

The system never implements a blocklist of "dangerous" commands or strings as a security control. All authorization is effect-based, evaluated by the policy engine described in the effect-taxonomy and policy-engine ADRs.

## Consequences

There is no list to keep "complete" and no false sense of security from one. Anyone tempted to add a quick blocklist as a stopgap must instead model the risk as a capability effect - slower, but the only version of this control that has held up over time.
