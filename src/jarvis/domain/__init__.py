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

from .audio import AudioChunk, AudioStream, Segment
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
from .evidence import Attempt, Candidate, EscalationRung, Evidence, EvidenceKind, Verdict
from .policy import Decision, DecisionReason, PolicyContext, evaluate
from .provenance import Classification, Provenance, Tainted, Trust
from .reasoning import ProviderProfile, TaskBudget
from .registry import CapabilityRegistry
from .speaker_id import SpeakerScore
from .transcript import Transcript
from .wake_word import WakeEvent

__all__ = [
    "ARGUMENT_DIGEST_KEY",
    "GENESIS_PREVIOUS_HASH",
    "Attempt",
    "AudioChunk",
    "AudioStream",
    "AuditChain",
    "AuditRecord",
    "AuditRecordNotSerializable",
    "AuditRecordTampered",
    "Candidate",
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
    "EscalationRung",
    "Evidence",
    "EvidenceKind",
    "JarvisError",
    "PolicyContext",
    "Provenance",
    "ProviderProfile",
    "Segment",
    "SpeakerScore",
    "TaintViolation",
    "Tainted",
    "TaskBudget",
    "Tier",
    "Transcript",
    "Trust",
    "Verdict",
    "WakeEvent",
    "digest_argument_value",
    "digest_value",
    "evaluate",
    "minimum_tier_for",
]
