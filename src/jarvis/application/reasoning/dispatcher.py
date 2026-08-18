"""The real dispatcher: wires the ladder, arbiter, router, and TaskBudget end-to-end.

``docs/architecture/m2-reasoning-layer.md`` section 5's deliverable #6
is "``TaskBudget`` + enforcement at the dispatcher." WP-30's own
domain type left "what one budget unit represents" deliberately
undecided, explicitly assigned to whichever work package "first builds
the dispatcher that actually spends a budget" -- this one. Decided
here: **one unit is one rung climbed**, not one provider call. Trying
two cloud providers at ``SECOND_PROVIDER`` and picking a winner via
:class:`~jarvis.application.reasoning.arbiter.Arbiter` still spends
exactly one unit, matching ``TaskBudget``'s own "how much asking is
left to spend" framing at the granularity a caller actually experiences
(one climb), not an internal implementation detail (how many providers
that climb happened to try).

**``DETERMINISTIC_FIX`` is a real, flagged gap, not silently
implemented or silently skipped**: the section-4 worked example
describes it as a non-LLM, pattern-matched fix ("the build output
already names the missing dependency"), and nothing in this repo --
no port, no domain type, no adapter -- implements any such mechanism.
Flagged during WP-37, before writing this dispatcher, and resolved
with direction: when the ladder proposes ``DETERMINISTIC_FIX``, this
class records a fixed ``FAILED`` attempt for it (spending no budget --
nothing real happened) and lets the ladder immediately climb past it
to ``SELF_REPAIR``, where real ``ReasoningPort``/``ValidationPort``
machinery takes over. A dedicated deterministic-fix mechanism is real,
undecided future work, not built speculatively here.

**Which specific :class:`~jarvis.domain.reasoning.ProviderProfile`
services which rung is an injected, overridable choice, not a global
policy** -- ``ModelRouter``'s own docstring explicitly left this
undecided, and nothing else in the recovered material specifies it.
The default this class is normally constructed with (see
``kernel``/composition-root wiring, not yet built) is: ``SELF_REPAIR``
tries the local provider alone (cheap, on-device, matches "self-repair"
as an inexpensive automatic retry); ``SECOND_PROVIDER`` tries both
cloud providers and lets the arbiter pick, matching section 3's
cross-vendor-heterogeneity principle and giving the arbiter something
real to select among. Every provider tried at any rung still goes
through :meth:`~jarvis.application.reasoning.router.ModelRouter.authorize_provider_call`
for real, so this specific assignment choice has no bearing on the
safety properties ADR-0014/ADR-0015/ADR-0038 guarantee -- those hold
for any rung-to-provider assignment, since gating happens per call, not
per assignment.

**Never silently continues past budget exhaustion** (acceptance
criterion #5): :meth:`run` checks ``budget.is_exhausted`` at the top of
every loop iteration, before proposing a next rung, and returns
whatever ``attempts`` were made so far the moment it is -- the partial
results a caller needs are exactly ``DispatchResult.attempts``, never
silently discarded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.domain.evidence import (
    Attempt,
    Candidate,
    EscalationRung,
    Evidence,
    EvidenceKind,
    Verdict,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from jarvis.application.reasoning.arbiter import Arbiter
    from jarvis.application.reasoning.ladder import EscalationLadder
    from jarvis.application.reasoning.router import ModelRouter
    from jarvis.domain.policy import PolicyContext
    from jarvis.domain.provenance import Tainted
    from jarvis.domain.reasoning import ProviderProfile, TaskBudget
    from jarvis.ports.reasoning import ReasoningPort
    from jarvis.ports.validation import ValidationPort

    ProvidersByRung = Mapping[EscalationRung, tuple[tuple[ProviderProfile, ReasoningPort], ...]]

_DISPATCHER_AUTHOR = "dispatcher"
_DETERMINISTIC_FIX_GAP_CONTENT = (
    "DETERMINISTIC_FIX has no real implementation in this repo (WP-37, flagged gap)."
)
_NO_PROVIDER_AUTHORIZED_CONTENT = (
    "No provider was authorized for this rung; every candidate call was denied by policy."
)


def _deterministic_fix_gap_attempt() -> Attempt:
    """Return the fixed, no-op Attempt recorded for DETERMINISTIC_FIX.

    See this module's own docstring for why: no real implementation of
    this rung exists anywhere in this repo.
    """
    candidate = Candidate(author=_DISPATCHER_AUTHOR, content=_DETERMINISTIC_FIX_GAP_CONTENT)
    return Attempt(
        rung=EscalationRung.DETERMINISTIC_FIX,
        candidate=candidate,
        evidence=(),
        verdict=Verdict.FAILED,
    )


def _no_provider_authorized_attempt(rung: EscalationRung) -> Attempt:
    """Return the placeholder Attempt recorded when every provider at ``rung`` was denied."""
    candidate = Candidate(author=_DISPATCHER_AUTHOR, content=_NO_PROVIDER_AUTHORIZED_CONTENT)
    evidence = Evidence(
        kind=EvidenceKind.VALIDATION_RESULT,
        author=_DISPATCHER_AUTHOR,
        weight=0.0,
        description="No candidate was generated: every provider's authorization was denied.",
    )
    return Attempt(
        rung=rung, candidate=candidate, evidence=(evidence,), verdict=Verdict.UNVERIFIABLE
    )


@dataclass(frozen=True)
class DispatchResult:
    """The real outcome of one Dispatcher.run() call.

    Attributes:
        attempts: Every ``Attempt`` made, in order -- the "partial
            results" acceptance criterion #5 requires be surfaced,
            even when the run stopped due to budget exhaustion.
        budget: The final ``TaskBudget`` state. ``budget.is_exhausted``
            tells a caller whether the run stopped because it ran out
            of budget rather than because the ladder itself terminated.
    """

    attempts: tuple[Attempt, ...]
    budget: TaskBudget


class Dispatcher:
    """Runs the real escalation loop for one task, end-to-end, respecting budget."""

    def __init__(
        self,
        ladder: EscalationLadder,
        arbiter: Arbiter,
        router: ModelRouter,
        validator: ValidationPort,
        providers: ProvidersByRung,
    ) -> None:
        """Store every collaborator this dispatcher orchestrates -- none constructed internally.

        Args:
            ladder: Decides which rung comes next, or that escalation
                should stop.
            arbiter: Selects the winning Candidate when a rung tries
                more than one provider.
            router: Authorizes every provider call through the real
                choke point (ADR-0039) before it happens.
            validator: Judges each generated Candidate. A single
                validator for the whole run -- which of the five real
                kinds (WP-33) to use is task-specific and is the
                caller's choice, not this class's to decide.
            providers: Which providers to try at ``SELF_REPAIR`` and
                ``SECOND_PROVIDER`` (``DETERMINISTIC_FIX`` never
                consults this -- see this module's docstring). An
                empty or missing entry for a rung means no provider is
                tried there at all, which is a valid, real outcome
                (:func:`_no_provider_authorized_attempt`), not an error.
        """
        self._ladder = ladder
        self._arbiter = arbiter
        self._router = router
        self._validator = validator
        self._providers = providers

    async def run(
        self, task: Tainted[str], budget: TaskBudget, context: PolicyContext
    ) -> DispatchResult:
        """Run the real escalation loop for ``task`` until it passes, is exhausted, or stops.

        Args:
            task: The task content, tagged with its real provenance --
                what ``router`` uses to decide whether a given cloud
                provider is authorized for this specific call.
            budget: The starting budget. Checked before every rung is
                attempted; never spent past its own limit silently
                (``TaskBudget.spend`` itself allows exceeding ``limit``,
                landing in ``is_exhausted``, which this loop then
                honors on its very next check).
            context: Facts about the environment authorization
                decisions are made in.

        Returns:
            A ``DispatchResult`` carrying every attempt made and the
            final budget state -- see this module's and
            ``DispatchResult``'s own docstrings for what each stopping
            condition looks like from a caller's side.
        """
        attempts: tuple[Attempt, ...] = ()
        while True:
            if budget.is_exhausted:
                return DispatchResult(attempts=attempts, budget=budget)
            rung = self._ladder.next_rung(attempts)
            if rung is None:
                return DispatchResult(attempts=attempts, budget=budget)
            if rung is EscalationRung.DETERMINISTIC_FIX:
                attempts = (*attempts, _deterministic_fix_gap_attempt())
                continue
            winner = await self._attempt_rung(rung, task, attempts, context)
            attempts = (*attempts, winner)
            budget = budget.spend(1)

    async def _attempt_rung(
        self,
        rung: EscalationRung,
        task: Tainted[str],
        prior_attempts: tuple[Attempt, ...],
        context: PolicyContext,
    ) -> Attempt:
        """Try every provider registered for `rung`, authorized for real, and return the winner."""
        candidate_attempts: list[Attempt] = []
        for profile, adapter in self._providers.get(rung, ()):
            decision = self._router.authorize_provider_call(profile, task, context)
            if not decision.granted:
                continue
            tainted_candidate = await adapter.generate(task.value, prior_attempts)
            candidate = tainted_candidate.value
            verdict, evidence = await self._validator.validate(candidate)
            candidate_attempts.append(
                Attempt(rung=rung, candidate=candidate, evidence=evidence, verdict=verdict)
            )

        if not candidate_attempts:
            return _no_provider_authorized_attempt(rung)

        winning_candidate = self._arbiter.select(tuple(candidate_attempts))
        return next(
            attempt for attempt in candidate_attempts if attempt.candidate is winning_candidate
        )
