"""The validation port: the seam between a Candidate and ground-truth judgement of it.

:class:`ValidationPort` is the one abstract boundary between "some real
way of judging a Candidate" (a build, a test run, a static analyzer, a
runtime check, a user-supplied script) and the rest of the system.
Nothing outside an adapter implementing this port knows or cares which
specific check actually produced a :class:`~jarvis.domain.evidence.Verdict`.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.validation`` (WP-33, not
yet built) for the concrete build/pytest/static/runtime/user_script
adapters that satisfy this port -- deliberately not named here: per
WP-30's scoping decision, which specific validator kinds exist is
adapter-level detail, and this Protocol is generic across all of them.

**Checked against ADR-0024, not just documented as compliant.** ADR-0024
requires that a reviewing model's output be "a concrete, executable
failing test case demonstrating the problem - never a prose verdict,
score, or opinion." Read carefully, that constraint is actually about
what a *reasoning provider acting as a reviewer* is allowed to hand
back (a :class:`~jarvis.ports.reasoning.ReasoningPort` concern: the
"failing test" itself becomes a new ``Candidate`` whose content is
test code, judged by *this* port once it exists) -- not literally a
constraint on ``ValidationPort`` itself, which represents *running*
something and reporting what happened, not producing a review opinion.

That said, the same failure mode ADR-0024 guards against -- a free-text
"trust me, it's broken" opinion masquerading as a real result -- is
worth resisting here too, and it is only partially something a type
signature can enforce. :meth:`ValidationPort.validate` returns a
:class:`~jarvis.domain.evidence.Verdict`, a closed three-member enum
(``PASSED``/``FAILED``/``UNVERIFIABLE``), not a free-text string or
score -- an implementation cannot return "looks probably fine" or a
0-100 confidence number, only one of exactly three discrete outcomes.
Stated honestly, not oversold: this does not, and cannot, prove a real
build/test/subprocess actually ran -- nothing in a ``Protocol``'s type
signature can distinguish "a real validator's ground-truth result"
from "a badly-behaved implementation that just returns ``Verdict.PASSED``
unconditionally." That distinction is an implementation-honesty
property, enforceable only by what a real adapter's contract test
actually exercises (WP-33), not by this Protocol alone -- named here
so it isn't silently assumed solved by the return type.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.evidence import Candidate, Evidence, Verdict


@runtime_checkable
class ValidationPort(Protocol):
    """A validator that judges a Candidate and reports its own Verdict plus supporting Evidence."""

    async def validate(self, candidate: Candidate) -> tuple[Verdict, tuple[Evidence, ...]]:
        """Judge ``candidate``, returning this validator's own Verdict and the Evidence behind it.

        Args:
            candidate: The candidate to judge.

        Returns:
            A tuple of ``(verdict, evidence)``. ``verdict`` is this
            validator's own outcome for ``candidate`` -- ``UNVERIFIABLE``
            is a real, distinct outcome (deliverable #7's
            unverifiable-task regime), not a stand-in for ``FAILED``,
            for a validator with no way to judge this candidate at
            all. ``evidence`` is every piece of
            :class:`~jarvis.domain.evidence.Evidence` gathered while
            reaching that verdict -- may be empty only when ``verdict``
            is ``UNVERIFIABLE`` and there is genuinely nothing to
            report; a ``PASSED``/``FAILED`` verdict with no supporting
            evidence at all would defeat this port's entire purpose
            (see this module's docstring on ADR-0024) and is not the
            behavior a real adapter should exhibit, though this
            Protocol's type signature cannot forbid it outright.
        """
        ...
