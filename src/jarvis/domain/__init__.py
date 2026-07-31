"""Domain ring: pure business rules and models.

This ring holds the concepts JARVIS reasons about: capabilities, effects,
policy tiers, provenance, and the ``Tainted[T]`` wrapper. It has no
knowledge of the outside world.

Constraints, enforced by tooling rather than convention:

* Imports stdlib only. No third-party packages, no ``ports``,
  ``application``, ``adapters``, ``plugin_api``, ``kernel``, ``ipc``, or
  ``cli`` imports (import-linter contract "C2 domain purity").
* No I/O and no async. Nothing here reads a file, opens a socket, or
  awaits anything.
* No wall-clock or randomness access (no ``datetime.now()``,
  ``time.time()``, ``uuid.uuid4()``, etc). Anything needing the current
  time or a fresh identifier takes a ``ClockPort`` / ``IdPort`` from the
  caller instead.
* No vendor names (no "openai", "anthropic", "chatgpt", "claude", "gpt").
"""

from __future__ import annotations

from .capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
    Tier,
    minimum_tier_for,
)
from .errors import JarvisError, TaintViolation
from .provenance import Classification, Provenance, Tainted, Trust

__all__ = [
    "CapabilityDescriptor",
    "CapabilityId",
    "CapabilityInvocation",
    "Classification",
    "Effect",
    "JarvisError",
    "Provenance",
    "TaintViolation",
    "Tainted",
    "Tier",
    "Trust",
    "minimum_tier_for",
]
