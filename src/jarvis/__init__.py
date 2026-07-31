"""JARVIS AI OS: a privacy-first, plugin-based agent kernel for Linux.

The package is organized as a set of concentric rings following Clean
Architecture / ports-and-adapters, with the dependency rule pointing
strictly inward:

    domain -> ports -> application -> adapters -> kernel -> ipc / cli

``domain`` is pure and stdlib-only; every other ring may depend on the
rings listed before it, and nothing may depend outward. See
``docs/architecture/`` for the full, approved design and ``docs/adr/``
for the individual decisions behind it.
"""
