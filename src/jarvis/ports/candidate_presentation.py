"""The candidate presentation port: the seam between competing Candidates and a human's choice.

ADR-0040's own "to-be-named presentation port, designed in M2's own
port layer alongside ``ReasoningPort``/``ValidationPort``," for
deliverable #7's unverifiable-task regime. Nothing outside an adapter
implementing this port knows or cares *how* candidates are presented
or a choice is collected -- TTS/text via the existing interaction
layer today (``jarvis.adapters.candidate_presentation``), a real
Console UI once M5 builds one, without this port or the selection
logic built against it changing at all (ADR-0040's whole point).

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.evidence import Candidate


class InvalidSelectionError(Exception):
    """Raised when a human's selection cannot be resolved to one of the presented candidates.

    Not a :class:`~jarvis.domain.errors.JarvisError` subclass: this is
    an adapter-level, real-world input-handling condition (a
    malformed or out-of-range choice), not a domain-level
    security/policy concern. Defined on the port rather than the
    adapter so that any future, non-TTS/text implementation of this
    port raises the same, technology-independent type.
    """


@runtime_checkable
class CandidatePresentationPort(Protocol):
    """Presents competing candidates to a human and returns which one they chose."""

    async def present_and_select(self, candidates: tuple[Candidate, ...]) -> Candidate:
        """Present every candidate in ``candidates`` and return the one a human selected.

        Args:
            candidates: Every candidate to present, in order. Never
                empty -- a caller with nothing to present has nothing
                to ask this port to do.

        Returns:
            Exactly one of ``candidates``, unmodified -- matching
            ADR-0023's "select, never merge" the same way
            :meth:`~jarvis.application.reasoning.arbiter.Arbiter.select`
            does, just with a human choosing instead of evidence
            scoring one (there is no validation evidence for an
            unverifiable task to score with).

        Raises:
            InvalidSelectionError: If the human's choice cannot be
                resolved to one of ``candidates``.
        """
        ...
