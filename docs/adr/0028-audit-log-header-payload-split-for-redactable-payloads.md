# ADR-0028: Audit log header/payload split for redactable payloads

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

If audit entries are single opaque blobs, redacting anything after the fact (e.g. in response to a data deletion request) breaks the hash chain and destroys tamper-evidence for every entry after it.

## Decision

Audit entries are split into a header (included in the hash chain, never redacted) and a payload (referenced by the header, redactable independently without breaking the chain).

## Consequences

A payload can later be redacted (e.g. for a right-to-erasure request) while the chain of headers remains intact and verifiable. The cost is a more complex two-part storage format than a single flat log entry.
