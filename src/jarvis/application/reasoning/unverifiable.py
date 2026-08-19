"""The unverifiable-task regime: parallel heterogeneous generation, escalation off, human picks.

Deliverable #7: "Unverifiable-task regime: parallel heterogeneous
drafting + user selection UI (escalation OFF by default here)."
Acceptance criterion #8: "Escalation is OFF by default for unverifiable
tasks -- asserted by test, not just documented."

:class:`UnverifiableTaskHandler` is a genuinely different code path
from :class:`~jarvis.application.reasoning.dispatcher.Dispatcher`, not
a variant of it: there is no :class:`~jarvis.application.reasoning.ladder.EscalationLadder`,
no rung, no self-repair loop, and no :class:`~jarvis.application.reasoning.arbiter.Arbiter`
anywhere in this module -- structurally, not just by convention,
"escalation off" for this regime, satisfying criterion #8 by the
simple fact that no escalation code exists here to turn on. Every
authorized provider is asked once, in parallel
(:func:`asyncio.gather`, matching "parallel" literally, not just
"non-sequential"), and the resulting candidates -- ungraded, since
there is no validator that can judge an unverifiable task, which is
exactly what makes it unverifiable -- are handed to a human via
:class:`~jarvis.ports.candidate_presentation.CandidatePresentationPort`
(ADR-0040) instead of :class:`~jarvis.application.reasoning.arbiter.Arbiter`'s
evidence-based scoring.

**Deliberately out of scope**: deciding *that* a task is unverifiable
in the first place (routing it here instead of to ``Dispatcher``).
Nothing in the recovered material or any real ADR specifies that
classification, and building one would be new, unresolved
architecture -- a future caller's job, not this class's.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jarvis.application.reasoning.router import ModelRouter
    from jarvis.domain.evidence import Candidate
    from jarvis.domain.policy import PolicyContext
    from jarvis.domain.provenance import Tainted
    from jarvis.domain.reasoning import ProviderProfile
    from jarvis.ports.candidate_presentation import CandidatePresentationPort
    from jarvis.ports.reasoning import ReasoningPort


class NoProviderAuthorizedError(Exception):
    """Raised when every provider's authorization was denied and there is nothing to present.

    Not a :class:`~jarvis.domain.errors.JarvisError` subclass: this is
    a real-world operational outcome (policy denied every candidate
    call for this task), not a domain-level taint/security violation
    -- matching :class:`~jarvis.ports.workspace.PatchApplicationFailedError`'s
    same reasoning.
    """


class UnverifiableTaskHandler:
    """Generates candidates in parallel from every authorized provider, human picks the winner."""

    def __init__(
        self,
        providers: tuple[tuple[ProviderProfile, ReasoningPort], ...],
        router: ModelRouter,
        presentation: CandidatePresentationPort,
    ) -> None:
        """Store the providers to try, the router that authorizes each, and the presentation port.

        Args:
            providers: Every provider to try, in parallel. Real
                heterogeneity (using genuinely different provider
                families, not several instances of the same one) is
                the caller's responsibility, matching how
                ``Dispatcher``'s own rung-to-provider assignment is an
                injected, caller's choice, not enforced here.
            router: The real ``ModelRouter`` every provider call is
                authorized through (ADR-0039) before it happens.
            presentation: Where candidates are presented and a human's
                choice is collected (ADR-0040).
        """
        self._providers = providers
        self._router = router
        self._presentation = presentation

    async def handle(self, task: Tainted[str], context: PolicyContext) -> Candidate:
        """Generate candidates from every authorized provider in parallel, human picks the winner.

        Raises:
            NoProviderAuthorizedError: If every provider's
                authorization was denied.
        """
        authorized_adapters: list[ReasoningPort] = []
        for profile, adapter in self._providers:
            decision = self._router.authorize_provider_call(profile, task, context)
            if decision.granted:
                authorized_adapters.append(adapter)

        if not authorized_adapters:
            msg = "No provider was authorized for this unverifiable task."
            raise NoProviderAuthorizedError(msg)

        tainted_candidates = await asyncio.gather(
            *(adapter.generate(task.value, ()) for adapter in authorized_adapters)
        )
        candidates = tuple(tainted.value for tainted in tainted_candidates)
        return await self._presentation.present_and_select(candidates)
