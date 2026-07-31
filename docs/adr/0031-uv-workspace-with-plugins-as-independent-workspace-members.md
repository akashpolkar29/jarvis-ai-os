# ADR-0031: uv workspace with plugins/* as independent workspace members

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Plugins are meant to be independently developed, versioned, and reviewed capability packages, not just modules living inside the main jarvis package - but without a real packaging boundary, that independence is just a convention.

## Decision

The project is a uv workspace with plugins/* configured as workspace members from Milestone 0 onward, even though no plugins exist yet, so that the packaging boundary is established before the first plugin needs to fit into it.

## Consequences

A future plugin can be added as a genuinely separate package with its own pyproject.toml and dependencies, resolved consistently with the rest of the workspace by uv. The cost is an empty workspace glob sitting in pyproject.toml for as long as no plugins exist, which is intentional scaffolding rather than dead configuration.
