# ADR-0010: Tainted[T] wrapper for provenance-carrying values

## Status

Accepted

## Date

2026-07-31

## Source

CLAUDE.md architecture summary, Milestone 0

## Context

Provenance metadata that lives in a side table or convention (e.g. "trust the caller to check") gets silently dropped the moment a value is copied, transformed, or passed through a function that wasn't written with it in mind.

## Decision

Every value with tracked provenance is represented as a generic Tainted[T] wrapper carrying both the payload and its provenance, so provenance travels with the value through the type system rather than through discipline.

## Consequences

mypy --strict can catch a function that silently unwraps or discards provenance where it shouldn't. The cost is wrapper ceremony throughout the domain and application layers - every function boundary that touches external data must thread Tainted[T] through instead of the bare type.
