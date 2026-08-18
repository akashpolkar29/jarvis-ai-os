"""The escalation ladder: a pure state machine deciding which rung to try next.

``docs/architecture/m2-reasoning-layer.md`` section 5's deliverable #4
names ``EscalationLadder`` as "a pure state machine, five stated
invariants" but the recovered material never lists what those five
are anywhere -- confirmed absent by re-reading the whole document
before writing this module. Enumerated here instead, each traced to a
real, already-decided source (an ADR, a domain type's own structure,
or the worked example in section 4), not invented to round out a
number:

1. **The first attempt at any task always starts at the cheapest
   rung.** ``next_rung(())`` is always ``DETERMINISTIC_FIX`` --
   matches ADR-0022's own "cheap deterministic fixes first" framing
   and the worked example's (section 4: rung 0 is tried before
   anything else).
2. **Only a ``PASSED`` verdict halts escalation.** ``FAILED`` and
   ``UNVERIFIABLE`` both mean "keep climbing" -- a validator that
   could not judge a candidate at all (``UNVERIFIABLE``) is not
   success, and treating it as a stop condition would silently accept
   an unproven candidate.
3. **Escalation only ever moves to the next rung in ADR-0022's fixed
   order, never skipping one.** Given the highest rung already
   attempted, the next proposed rung is exactly one step higher --
   never straight from ``DETERMINISTIC_FIX`` to ``SECOND_PROVIDER``,
   skipping ``SELF_REPAIR``. This is ADR-0022 ("deterministic fixes,
   then self-repair, before a second provider") made structurally
   impossible to violate, not left implicit in prose.
4. **Escalation is monotonic.** The next proposed rung is always
   strictly higher than every rung already attempted -- no rung is
   revisited once climbed past. A rung is attempted at most once per
   task in this model; there is no "retry the same rung" concept
   anywhere in the recovered material or the real
   :class:`~jarvis.domain.evidence.EscalationRung` domain type (WP-30),
   which enumerates exactly three discrete, ordered rungs with no
   notion of a repeat round.
5. **Escalation is bounded.** Once ``SECOND_PROVIDER`` -- the highest
   rung :class:`~jarvis.domain.evidence.EscalationRung` defines -- has
   been attempted and did not pass, ``next_rung`` returns ``None``:
   there is no rung beyond it, and the ladder must terminate rather
   than loop or invent one.

**Deliberately out of scope, per deliverable #6's own split**: budget
awareness. ``TaskBudget`` (WP-30) is "enforcement at the dispatcher,"
not the ladder -- this class answers "what rung comes next, given the
climb so far," never "is there budget left to try it." A dispatcher
(WP-37, not yet built) is responsible for checking
:attr:`~jarvis.domain.reasoning.TaskBudget.is_exhausted` before acting
on whatever this class returns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.domain.evidence import EscalationRung, Verdict

if TYPE_CHECKING:
    from jarvis.domain.evidence import Attempt

_HIGHEST_RUNG = EscalationRung.SECOND_PROVIDER


class EscalationLadder:
    """Decides which EscalationRung to try next for a task, or that escalation should stop."""

    def next_rung(self, attempts: tuple[Attempt, ...]) -> EscalationRung | None:
        """Return the next rung to try, given every attempt made so far, or None to stop.

        Args:
            attempts: Every :class:`~jarvis.domain.evidence.Attempt`
                made at this task so far, in any order -- at most one
                per rung (see this module's docstring, invariant 4).
                Empty for a first attempt.

        Returns:
            The next :class:`~jarvis.domain.evidence.EscalationRung`
            to try, or ``None`` if escalation should stop -- either
            because some attempt already ``PASSED``, or because
            ``SECOND_PROVIDER`` was already attempted and did not.
        """
        if any(attempt.verdict is Verdict.PASSED for attempt in attempts):
            return None
        if not attempts:
            return EscalationRung.DETERMINISTIC_FIX
        highest_attempted = max(attempt.rung for attempt in attempts)
        if highest_attempted is _HIGHEST_RUNG:
            return None
        return EscalationRung(highest_attempted + 1)
