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

from .audit import (
    ARGUMENT_DIGEST_KEY,
    GENESIS_PREVIOUS_HASH,
    AuditChain,
    AuditRecord,
    ChainVerificationResult,
    digest_argument_value,
    digest_value,
)
from .capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
    Tier,
    minimum_tier_for,
)
from .errors import (
    AuditRecordNotSerializable,
    AuditRecordTampered,
    CapabilityAlreadyRegistered,
    CapabilityNotRegistered,
    JarvisError,
    TaintViolation,
)
from .policy import Decision, DecisionReason, PolicyContext, evaluate
from .provenance import Classification, Provenance, Tainted, Trust
from .registry import CapabilityRegistry

__all__ = [
    "ARGUMENT_DIGEST_KEY",
    "GENESIS_PREVIOUS_HASH",
    "AuditChain",
    "AuditRecord",
    "AuditRecordNotSerializable",
    "AuditRecordTampered",
    "CapabilityAlreadyRegistered",
    "CapabilityDescriptor",
    "CapabilityId",
    "CapabilityInvocation",
    "CapabilityNotRegistered",
    "CapabilityRegistry",
    "ChainVerificationResult",
    "Classification",
    "Decision",
    "DecisionReason",
    "Effect",
    "JarvisError",
    "PolicyContext",
    "Provenance",
    "TaintViolation",
    "Tainted",
    "Tier",
    "Trust",
    "digest_argument_value",
    "digest_value",
    "evaluate",
    "minimum_tier_for",
]
