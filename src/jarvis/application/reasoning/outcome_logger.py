"""The outcome logger: non-authoritative engineering telemetry only, per ADR-0039.

``docs/architecture/m2-reasoning-layer.md`` section 5's deliverable
#11 ("structured outcome logging for future analysis... explicitly no
adaptation/learning in M2 itself") risked becoming a second, unaudited
record of what M2 did -- ADR-0039 closed that risk by narrowing
``OutcomeLogger`` explicitly to non-authoritative engineering
telemetry: *"which rung was reached, latency, pass/fail"* -- and
stating it "must never record or substitute for an authorization-
relevant event. The tamper-evident ``AuditChain`` remains the single
source of truth for 'was this egress authorized'."

That narrowing is structurally enforced here, not merely documented:
:class:`Outcome` has exactly three fields --
:class:`~jarvis.domain.evidence.EscalationRung`, a latency in seconds,
and a :class:`~jarvis.domain.evidence.Verdict`. There is no field for
a task's content, a Candidate's content, a provider's identity, a
``Decision``, a ``Tier``, or a ``PolicyContext`` -- nothing this class
could pass to a real :class:`~jarvis.ports.outcome.OutcomeSinkPort`
implementation could ever be mistaken for "was this call authorized."
If a future change to this file ever needs to log something
authorization-relevant, that is exactly the ambiguity-stop ADR-0039
calls for, not something to route around by widening ``Outcome``.

Latency measurement itself is deliberately not this class's job:
:meth:`OutcomeLogger.record` takes an already-computed
``latency_seconds`` rather than measuring one with a clock. Whoever
times a real rung attempt (a future dispatcher integration, not built
in this work package) needs its own real clock dependency to do that
-- inventing one here, unused by anything real yet, would be
speculative scope this work package was not asked for.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jarvis.domain.evidence import EscalationRung, Verdict
    from jarvis.ports.outcome import OutcomeSinkPort


@dataclass(frozen=True)
class Outcome:
    """One rung's non-authoritative engineering telemetry -- nothing else, by design.

    Attributes:
        rung: Which rung was reached.
        latency_seconds: How long that rung took, in seconds.
        verdict: Whether it passed, failed, or was unverifiable.

    Raises:
        ValueError: If ``latency_seconds`` is negative.
    """

    rung: EscalationRung
    latency_seconds: float
    verdict: Verdict

    def __post_init__(self) -> None:
        """Validate ``latency_seconds`` is non-negative."""
        if self.latency_seconds < 0:
            msg = f"Outcome.latency_seconds must be non-negative: {self.latency_seconds!r}"
            raise ValueError(msg)


class OutcomeLogger:
    """Records non-authoritative engineering telemetry about M2 reasoning outcomes."""

    def __init__(self, sink: OutcomeSinkPort) -> None:
        """Store the real sink every outcome is recorded to.

        Args:
            sink: Owned by the caller, matching every other real
                consumer of a port in this repo -- this class never
                constructs its own.
        """
        self._sink = sink

    def record(self, outcome: Outcome) -> None:
        """Record ``outcome`` to the injected sink, as a plain, JSON-serializable mapping."""
        entry = {
            "rung": outcome.rung.name,
            "latency_seconds": outcome.latency_seconds,
            "verdict": outcome.verdict.value,
        }
        self._sink.record(entry)
