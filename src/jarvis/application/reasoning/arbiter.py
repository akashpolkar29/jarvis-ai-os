"""The arbiter: selects exactly one Candidate from competing attempts, never merges.

``docs/architecture/m2-reasoning-layer.md`` section 7 names ``Arbiter``
as "selection only" with an "author-exclusion rule (never merges
implementations)." Directly implements two already-accepted ADRs:

* **ADR-0023 ("Select, never merge")**: :meth:`Arbiter.select` returns
  one of its input candidates exactly as given -- the same object,
  never a reconstruction or combination of two. There is no code path
  here that reads more than one candidate's ``content`` at once, which
  is what makes "never merge" structurally true rather than a rule
  this class merely documents (acceptance criterion #2: output is
  byte-identical to one input candidate, always).
* **ADR-0025 ("A provider's own tests carry zero weight scoring its
  own candidate")**: :meth:`_score` excludes any
  :class:`~jarvis.domain.evidence.Evidence` whose ``author`` matches
  the candidate's own ``author`` -- self-authored evidence contributes
  nothing (acceptance criterion #3).

**Also covers acceptance criterion #4** ("``MODEL_OPINION`` evidence
can never change a selection"), not explicitly assigned to this work
package by name but squarely this class's own concern: :meth:`_score`
only ever sums ``VALIDATION_RESULT`` evidence -- ``MODEL_OPINION``
evidence contributes zero weight unconditionally, regardless of
author, structurally enforcing section 2's "make it structurally
impossible to confuse [model agreement with passing validation]"
principle rather than merely documenting it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.domain.evidence import EvidenceKind

if TYPE_CHECKING:
    from jarvis.domain.evidence import Attempt, Candidate


class Arbiter:
    """Selects exactly one Candidate from a set of competing attempts, unmodified."""

    def select(self, attempts: tuple[Attempt, ...]) -> Candidate:
        """Select and return exactly one Candidate from ``attempts``, unmodified.

        Args:
            attempts: Every competing attempt to choose among (e.g.
                heterogeneous candidates from multiple providers at
                the same rung). Each attempt's own ``evidence`` is
                what scores its own ``candidate`` -- see :meth:`_score`.

        Returns:
            The ``candidate`` of whichever attempt scores highest,
            returned exactly as given (ADR-0023) -- never a merge of
            two. Ties resolve to the first-scoring-highest attempt in
            ``attempts``' own order, deterministically.

        Raises:
            ValueError: If ``attempts`` is empty. Selecting from
                nothing is not a meaningful default and must never be
                invented silently, matching
                :meth:`~jarvis.domain.provenance.Provenance.merge_all`'s
                own precedent for the same situation.
        """
        if not attempts:
            msg = "Arbiter.select() requires at least one Attempt."
            raise ValueError(msg)
        best = max(attempts, key=self._score)
        return best.candidate

    @staticmethod
    def _score(attempt: Attempt) -> float:
        """Sum ``attempt``'s VALIDATION_RESULT evidence weight, excluding self-authored evidence.

        ``MODEL_OPINION`` evidence is never summed at all (criterion
        #4). Evidence whose ``author`` equals ``attempt.candidate.author``
        is excluded regardless of kind (ADR-0025, criterion #3) -- a
        provider's own validation of its own candidate does not count
        as independent signal.
        """
        return sum(
            evidence.weight
            for evidence in attempt.evidence
            if evidence.kind is EvidenceKind.VALIDATION_RESULT
            and evidence.author != attempt.candidate.author
        )
