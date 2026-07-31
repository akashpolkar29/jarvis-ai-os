# ADR-0017: Secrets live only in the system keyring, referenced never stored

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Secrets that end up as plain values anywhere in the system (source, config, database rows, log lines) create a second place that needs to be secured as tightly as the keyring itself, and history shows secondary copies are the ones that leak.

## Decision

Secrets are stored only in the system keyring. Everywhere else in the system - domain objects, the database, the audit log, source code - a secret is represented by a reference/handle, never by its value.

## Consequences

Any code that needs a secret's actual value must go through the keyring adapter at the point of use, which is a deliberate extra hop. In exchange, a full dump of the database or audit log never yields a usable secret.
