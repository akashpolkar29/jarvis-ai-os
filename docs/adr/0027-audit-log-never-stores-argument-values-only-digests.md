# ADR-0027: Audit log never stores argument values, only digests

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

An audit log that stores full argument values becomes, by construction, a second copy of every secret and every piece of sensitive data that ever flowed through the system - defeating the keyring and classification controls elsewhere.

## Decision

The audit log records only digests (hashes) of capability invocation arguments, never the argument values themselves.

## Consequences

A full compromise of the audit log does not leak the sensitive data it references. The cost is that the audit log alone cannot reconstruct "what exactly was the value" for a forensic replay - that requires cross-referencing with whatever system produced the value, if it still exists.
