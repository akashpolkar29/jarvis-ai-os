"""Provider and budget vocabulary for the M2 reasoning layer.

Kept separate from :mod:`jarvis.domain.evidence` deliberately -- a
:class:`ProviderProfile` (who can be asked) and a :class:`TaskBudget`
(how much asking is left to spend) are routing/spend metadata, not
scoring vocabulary, the same distinction that keeps ``capability.py``,
``policy.py``, and ``provenance.py`` as three files rather than one.

Field sets here are deliberately minimal. The recovered M2 design
(``docs/architecture/m2-reasoning-layer.md``) names both types
(deliverables #1 and #6) but never specifies their exact fields --
inventing a richer shape now (a cost model, a latency estimate, a
capability-tag list) would be designing ahead of the application-layer
work (WP-32 and later) that actually needs those fields, which is
exactly the kind of speculative detail this project's rolling-wave
principle exists to avoid. Extend these types when a real consumer
needs more, not before.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderProfile:
    """Static, registered-once metadata about one reasoning provider.

    The domain-level analogue of :class:`~jarvis.domain.capability.CapabilityDescriptor`:
    a provider's identity and shape, not a live connection to it (that
    is :class:`~jarvis.ports.reasoning.ReasoningPort`'s job, not yet
    built as of WP-30).

    Attributes:
        name: An opaque identifier for this provider -- never a vendor
            name (ADR-0021). This module cannot enforce that at
            construction time any more than ``Evidence.author`` or
            ``Candidate.author`` can; it is enforced by
            ``tests/meta/test_source_invariants.py``'s repo-wide grep,
            not by validation here.
        is_local: Whether this provider runs entirely on-device. A
            local provider has no egress effect at all, which is
            directly relevant to ADR-0014/ADR-0015/ADR-0038's
            Classification-based gating: only non-local (cloud)
            providers are ever candidates for ``EGRESS_SENSITIVE``/
            ``EGRESS_SECRET``-gated capabilities in the first place.

    Raises:
        ValueError: If ``name`` is empty.
    """

    name: str
    is_local: bool

    def __post_init__(self) -> None:
        """Validate ``name`` is non-empty."""
        if not self.name:
            msg = "ProviderProfile.name must not be empty."
            raise ValueError(msg)


@dataclass(frozen=True)
class TaskBudget:
    """How much of a task's reasoning budget has been spent, in pure domain terms.

    Immutable, like :class:`~jarvis.domain.provenance.Provenance` and
    :class:`~jarvis.domain.provenance.Tainted`: :meth:`spend` returns a
    new ``TaskBudget`` rather than mutating this one, so a caller can
    never lose track of a budget's prior state by accident.

    What one budget "unit" represents (a rung climbed, a provider call,
    a cost bucket) is deliberately undecided here -- that is a real
    design choice for whichever work package first builds the
    dispatcher that actually spends a budget (WP-37 in the WP-28 plan),
    not this one. This type only has to make exhaustion representable
    and checkable in pure domain terms, which does not require knowing
    what a unit means.

    Attributes:
        limit: The total budget available, non-negative.
        spent: How much has been spent so far, non-negative. May equal
            or exceed ``limit`` -- that is exactly the exhausted state
            :attr:`is_exhausted` reports, not a construction error.

    Raises:
        ValueError: If ``limit`` or ``spent`` is negative.
    """

    limit: int
    spent: int = 0

    def __post_init__(self) -> None:
        """Validate ``limit`` and ``spent`` are non-negative."""
        if self.limit < 0:
            msg = f"TaskBudget.limit must be non-negative: {self.limit!r}"
            raise ValueError(msg)
        if self.spent < 0:
            msg = f"TaskBudget.spent must be non-negative: {self.spent!r}"
            raise ValueError(msg)

    @property
    def remaining(self) -> int:
        """Return how much budget is left, floored at zero."""
        return max(0, self.limit - self.spent)

    @property
    def is_exhausted(self) -> bool:
        """Return whether this budget has nothing left to spend."""
        return self.spent >= self.limit

    def spend(self, amount: int) -> TaskBudget:
        """Return a new ``TaskBudget`` with ``amount`` more spent.

        Args:
            amount: How much to spend, non-negative. Spending past
                ``limit`` is allowed -- the result is simply exhausted,
                not rejected -- so a caller never has to special-case
                "the last unit" before calling this.

        Returns:
            A new ``TaskBudget`` with the same ``limit`` and
            ``spent + amount``.

        Raises:
            ValueError: If ``amount`` is negative.
        """
        if amount < 0:
            msg = f"TaskBudget.spend() amount must be non-negative: {amount!r}"
            raise ValueError(msg)
        return TaskBudget(limit=self.limit, spent=self.spent + amount)
