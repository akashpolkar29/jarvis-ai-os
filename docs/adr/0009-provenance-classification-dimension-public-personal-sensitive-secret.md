# ADR-0009: Provenance classification dimension: PUBLIC / PERSONAL / SENSITIVE / SECRET

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Trust (where a value came from) and sensitivity (what it would cost to leak) are different axes - a SECRET can be USER_DIRECT (a password the user just typed) and an UNTRUSTED_EXTERNAL value can still be PUBLIC (a public web page).

## Decision

Every value additionally carries a classification - PUBLIC, PERSONAL, SENSITIVE, or SECRET - independent of its trust level, together forming its full provenance.

## Consequences

The privacy policy (see the cloud-routing ADRs) can be expressed purely in terms of classification, decoupled from trust. This doubles the tagging burden at every ingestion point relative to a single-axis model, which is accepted as the cost of getting privacy routing right.
