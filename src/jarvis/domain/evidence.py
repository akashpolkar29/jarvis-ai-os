"""The M2 escalation ladder's scoring vocabulary: what was tried, and how it was judged.

An :class:`Attempt` is one climb of the ladder for a task: at a given
:class:`EscalationRung`, some :class:`Candidate` was produced and
judged against a set of :class:`Evidence`, producing a :class:`Verdict`.
This module holds only that scoring vocabulary -- it says nothing about
*how* a ladder decides to escalate, how an arbiter selects among
candidates, or how a provider is chosen. Those are application-layer
concerns (``application.reasoning``, not yet built as of WP-30) that
consume these types; this module only has to make the types themselves
constructible and honest about what they represent.

Deliberately scoped away from provider/budget vocabulary: see
:mod:`jarvis.domain.reasoning` for :class:`~jarvis.domain.reasoning.ProviderProfile`
and :class:`~jarvis.domain.reasoning.TaskBudget`, which are conceptually
distinct (routing/spend metadata, not scoring vocabulary) and were kept
in a separate file for the same reason ``capability.py``/``policy.py``/
``provenance.py`` are three files, not one.

A real, stated gap, not silently smoothed over: the WP-28 planning
pass's cost-model worked example (``docs/architecture/m2-reasoning-layer.md``
section 4) refers to "rungs 2-5" without ever naming what they are --
only rung 0 (deterministic fix) and rung 1 (self-repair) are actually
described anywhere in the recovered design material. ADR-0022 names
exactly three phases: deterministic fixes, self-repair, and escalation
to a second provider. :class:`EscalationRung` below encodes only those
three, evidenced phases. Whatever finer-grained rungs the cost model's
"2-5" implies (most plausibly sub-steps of second-provider consultation
-- generate, review, arbiter-select) are not decided anywhere in the
recovered material, and are not invented here. Extending this enum is
real, undecided design work for whichever work package first builds
``application.reasoning.ladder`` (WP-34 in the WP-28 plan), not this one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum


class EscalationRung(IntEnum):
    """Where in the escalation ladder one attempt sits, cheapest first.

    Ordered so that a higher rung is strictly more expensive/invasive
    than a lower one (ADR-0022: deterministic fixes are tried before
    self-repair, which is tried before consulting a second provider).
    See this module's docstring for why only these three members exist.
    """

    DETERMINISTIC_FIX = 0
    SELF_REPAIR = 1
    SECOND_PROVIDER = 2


class EvidenceKind(Enum):
    """What kind of signal a piece of :class:`Evidence` represents.

    The two kinds the recovered M2 design and its acceptance criteria
    actually name: a validation result (a build, test, lint, or
    execution outcome -- section 2's "ground truth about behaviour")
    and a model opinion (acceptance criterion #4: "MODEL_OPINION
    evidence can never change a selection"). Not a :class:`~enum.Flag`
    -- one piece of Evidence is exactly one kind, never a combination.
    """

    VALIDATION_RESULT = "validation_result"
    MODEL_OPINION = "model_opinion"


class Verdict(Enum):
    """The outcome of judging a :class:`Candidate` against its :class:`Evidence`.

    ``UNVERIFIABLE`` is a real, distinct outcome, not a stand-in for
    ``FAILED`` -- it is what deliverable #7's "unverifiable-task
    regime" exists to handle: a task with no available validator that
    could ever produce a ``PASSED``/``FAILED`` verdict at all.
    """

    PASSED = "passed"
    FAILED = "failed"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True)
class Evidence:
    """One piece of evidence about a :class:`Candidate`, from one author.

    Attributes:
        kind: What kind of signal this is.
        author: An opaque identifier for whoever produced this evidence
            -- a provider name, a validator name, or "human". Never a
            vendor name (ADR-0021): this module has no way to enforce
            that at construction time, the same way ``CapabilityId``
            cannot forbid every possible bad token -- it is enforced by
            ``tests/meta/test_source_invariants.py``'s repo-wide grep,
            not by validation here. Needed so a future arbiter can
            implement ADR-0025 (a provider's own tests carry zero
            weight scoring its own candidate) by comparing this against
            ``Candidate.author``.
        weight: How much this evidence should count, non-negative. Not
            necessarily final -- ADR-0025's zero-weighting is an
            application-layer scoring decision made by comparing
            ``author`` against a ``Candidate``'s own author, not
            something this type can enforce on its own (it has no
            reference to any particular candidate).
        description: A human-readable account of what this evidence
            actually shows. Must be non-empty, matching
            ``CapabilityDescriptor.description``'s precedent.

    Raises:
        ValueError: If ``author`` or ``description`` is empty, or if
            ``weight`` is negative. Plain ``ValueError``, not a
            ``JarvisError`` subclass -- this is malformed-literal
            validation at construction time, the same reasoning as
            ``CapabilityId``'s and ``WakeEvent``'s ``__post_init__``,
            not a runtime security event.
    """

    kind: EvidenceKind
    author: str
    weight: float
    description: str

    def __post_init__(self) -> None:
        """Validate ``author``/``description`` are non-empty and ``weight`` is non-negative."""
        if not self.author:
            msg = "Evidence.author must not be empty."
            raise ValueError(msg)
        if not self.description:
            msg = "Evidence.description must not be empty."
            raise ValueError(msg)
        if self.weight < 0:
            msg = f"Evidence.weight must be non-negative: {self.weight!r}"
            raise ValueError(msg)


@dataclass(frozen=True)
class Candidate:
    """One proposed solution, from one author, at one rung of the ladder.

    Attributes:
        author: An opaque identifier for whoever produced this
            candidate -- never a vendor name (ADR-0021), same caveat as
            ``Evidence.author``.
        content: The candidate's actual content (e.g. a patch, a
            diff, a plain-text answer). Kept as ``str``, not a richer
            type: domain is stdlib-only (ADR-0029), and richer
            candidate shapes (a real diff object, a file tree) are an
            adapter-layer concern, not decided here.

    Raises:
        ValueError: If ``author`` or ``content`` is empty.
    """

    author: str
    content: str

    def __post_init__(self) -> None:
        """Validate ``author`` and ``content`` are non-empty."""
        if not self.author:
            msg = "Candidate.author must not be empty."
            raise ValueError(msg)
        if not self.content:
            msg = "Candidate.content must not be empty."
            raise ValueError(msg)


@dataclass(frozen=True)
class Attempt:
    """One full climb of one rung: a candidate, its evidence, and the resulting verdict.

    Attributes:
        rung: Which rung of the ladder this attempt was made at.
        candidate: The candidate produced at this rung.
        evidence: Every piece of evidence gathered about ``candidate``,
            in no particular order.
        verdict: The outcome of judging ``candidate`` against
            ``evidence``.
    """

    rung: EscalationRung
    candidate: Candidate
    evidence: tuple[Evidence, ...]
    verdict: Verdict
