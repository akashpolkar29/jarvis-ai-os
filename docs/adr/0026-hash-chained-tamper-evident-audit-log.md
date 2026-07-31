# ADR-0026: Hash-chained, tamper-evident audit log

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

An audit log that can be edited after the fact without detection is not useful evidence in an incident review - anyone with write access to the log (including a compromised process) could rewrite history.

## Decision

Every capability invocation is recorded in an audit log where each entry includes a hash of the previous entry, forming a tamper-evident chain - any edit or deletion of a past entry is detectable by hash mismatch.

## Consequences

Incident review can trust the audit log's integrity without a separate, harder-to-maintain signing infrastructure. The cost is that legitimate log rotation/archival must preserve the chain (or explicitly start a new one), not silently truncate it.
