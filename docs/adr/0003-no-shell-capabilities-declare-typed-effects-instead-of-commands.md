# ADR-0003: No shell: capabilities declare typed effects instead of commands

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

A generic "run this shell command" capability is the single most dangerous primitive an LLM-driven agent can be given - it collapses every possible action into one unauditable string, and any blocklist of "dangerous" commands is provably incomplete.

## Decision

Agents are never given shell access. Every capability instead declares its effects using a fixed, typed vocabulary (READ_LOCAL, WRITE_LOCAL, DESTRUCTIVE, IRREVERSIBLE, CREDENTIAL, EGRESS_SENSITIVE, etc.), and the policy engine evaluates those declared effects - never the literal action being taken.

## Consequences

Every capability's worst-case behavior is knowable statically from its declared effects, before it ever runs. The limitation is expressiveness: a capability that doesn't fit the existing effect vocabulary needs the vocabulary extended (via ADR), not worked around with a custom flag.
